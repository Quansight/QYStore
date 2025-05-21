from pycrdt_websocket.ystore import BaseYStore, YDocNotFound
from collections.abc import AsyncIterator, Awaitable
from logging import Logger, getLogger
from typing import Callable
import brotli
import time
import anyio
from anyio import TASK_STATUS_IGNORED, Event, Lock, create_task_group
from anyio.abc import TaskStatus
from sqlite_anyio import Connection, connect, exception_logger
from pycrdt import Doc
from .utils import get_new_path
from traitlets.config import LoggingConfigurable
from traitlets import Unicode, Int
import os

class QStore(BaseYStore):
    """A YStore which uses an SQLite database.
    Unlike file-based YStores, the Y updates of all documents are stored in the same database.

    Subclass to point to your database file:

    ```py
    class MySQLiteYStore(SQLiteYStore):
        db_path = "path/to/my_ystore.db"
    ```
    """

    db_path: str = "qstore.db"
    # Determines the "time to live" for all documents, i.e. how recent the
    # latest update of a document must be before purging document history.
    # Defaults to never purging document history (None).
    document_ttl: int | None = None
    # Interval at which checkpoints are created for efficient document loading
    checkpoint_interval = 100
    # Counter to keep track of updates since the last checkpoint
    _update_counter = 0
    path: str
    lock: Lock
    db_initialized: Event | None
    _db: Connection
    # Optional callbacks for compressing and decompressing data, default: no compression
    _compress: Callable[[bytes], bytes] | None = None
    _decompress: Callable[[bytes], bytes] | None = None

    def __init__(
        self,
        path: str,
        metadata_callback: Callable[[], Awaitable[bytes] | bytes] | None = None,
        log: Logger | None = None,
    ) -> None:
        """Initialize the object.

        Arguments:
            path: The file path used to store the updates.
            metadata_callback: An optional callback to call to get the metadata.
            log: An optional logger.
        """
        self.path = path
        self.metadata_callback = metadata_callback
        self.log = log or getLogger(__name__)
        self.lock = Lock()
        self.db_initialized = None

    async def apply_checkpointed_updates(self, ydoc: Doc) -> None:
        """Apply the latest checkpoint (if any) and then all subsequent updates to the YDoc."""
        if self.db_initialized is None:
            raise RuntimeError("YStore not started")
        await self.db_initialized.wait()

        found_any = False
        async with self.lock:
            async with self._db:
                cursor = await self._db.cursor()

                # 1) Load latest checkpoint, if present
                await cursor.execute(
                    "SELECT checkpoint, timestamp FROM ycheckpoints WHERE path = ?",
                    (self.path,),
                )
                row = await cursor.fetchone()
                if row:
                    checkpoint_blob, last_ts = row
                    ydoc.apply_update(checkpoint_blob)
                    found_any = True
                else:
                    last_ts = 0.0

                # 2) Apply all updates after the checkpoint timestamp
                await cursor.execute(
                    "SELECT yupdate, metadata, timestamp "
                    "FROM yupdates "
                    "WHERE path = ? AND timestamp > ? "
                    "ORDER BY timestamp ASC",
                    (self.path, last_ts),
                )
                for update, metadata, timestamp in await cursor.fetchall():
                    ydoc.apply_update(update)
                    found_any = True

        if not found_any:
            # no checkpoint and no updates ⇒ document doesn't exist
            raise YDocNotFound

    async def start(
        self,
        *,
        task_status: TaskStatus[None] = TASK_STATUS_IGNORED,
        from_context_manager: bool = False,
    ):
        """Start the SQLiteYStore.

        Arguments:
            task_status: The status to set when the task has started.
        """
        self.db_initialized = Event()
        if from_context_manager:
            assert self._task_group is not None
            self._task_group.start_soon(self._init_db)
            task_status.started()
            self.started.set()
            return

        async with self._start_lock:
            if self._task_group is not None:
                raise RuntimeError("YStore already running")
            async with create_task_group() as self._task_group:
                self._task_group.start_soon(self._init_db)
                task_status.started()
                self.started.set()
                await self.stopped.wait()

    async def stop(self) -> None:
        """Stop the store."""
        if self.db_initialized is not None and self.db_initialized.is_set():
            await self._db.close()
        await super().stop()

    async def _init_db(self):
        def brotli_compress_q1(data: bytes) -> bytes:
            return brotli.compress(data, quality=1)
        self.register_compression_callbacks(compress=brotli_compress_q1, decompress=brotli.decompress)
        create_db = False
        move_db = False
        if not await anyio.Path(self.db_path).exists():
            create_db = True
        else:
            async with self.lock:
                db = await connect(
                    self.db_path,
                    exception_handler=exception_logger,
                    log=self.log,
                )
                async with db:
                    cursor = await db.cursor()
                    await cursor.execute(
                        "SELECT count(name) FROM sqlite_master "
                        "WHERE type='table' and name='yupdates'"
                    )
                    table_exists = (await cursor.fetchone())[0]
                    if table_exists:
                        await cursor.execute("pragma user_version")
                        version = (await cursor.fetchone())[0]
                        if version != self.version:
                            move_db = True
                            create_db = True
                        else:
                            await cursor.execute(
                                "SELECT count(name) FROM sqlite_master "
                                "WHERE type='table' AND name='ycheckpoints'"
                            )
                            ckpt_exists = (await cursor.fetchone())[0]
                            if not ckpt_exists:
                                create_db = True
                    else:
                        create_db = True
                await db.close()
        if move_db:
            new_path = await get_new_path(self.db_path)
            self.log.warning("YStore version mismatch, moving %s to %s", self.db_path, new_path)
            await anyio.Path(self.db_path).rename(new_path)
        if create_db:
            async with self.lock:
                db = await connect(
                    self.db_path,
                    exception_handler=exception_logger,
                    log=self.log,
                )
                async with db:
                    cursor = await db.cursor()
                    await cursor.execute("PRAGMA auto_vacuum = FULL")
                    await cursor.execute("VACUUM")
                    await cursor.execute(
                        "CREATE TABLE yupdates (path TEXT NOT NULL, yupdate BLOB, "
                        "metadata BLOB, timestamp REAL NOT NULL)"
                    )
                    await cursor.execute(
                        "CREATE INDEX idx_yupdates_path_timestamp ON yupdates (path, timestamp)"
                    )
                    await cursor.execute(
                        "CREATE TABLE ycheckpoints ("
                        "path TEXT NOT NULL, "
                        "checkpoint BLOB NOT NULL, "
                        "timestamp REAL NOT NULL, "
                        "PRIMARY KEY(path)"
                        ")"
                    )
                    await cursor.execute(f"PRAGMA user_version = {self.version}")
            self._db = db
        else:
            self._db = await connect(
                self.db_path,
                exception_handler=exception_logger,
                log=self.log,
            )
        assert self.db_initialized is not None
        self.db_initialized.set()

    def register_compression_callbacks(
        self, compress: Callable[[bytes], bytes], decompress: Callable[[bytes], bytes]
    ) -> None:
        if not callable(compress) or not callable(decompress):
            raise TypeError("Both compress and decompress must be callable.")
        self._compress = compress
        self._decompress = decompress

    async def read(self) -> AsyncIterator[tuple[bytes, bytes, float]]:
        """Async iterator for reading the store content.

        Returns:
            A tuple of (update, metadata, timestamp) for each update.
        """
        if self.db_initialized is None:
            raise RuntimeError("YStore not started")
        await self.db_initialized.wait()
        try:
            async with self.lock:
                found = False
                async with self._db:
                    cursor = await self._db.cursor()
                    await cursor.execute(
                        "SELECT yupdate, metadata, timestamp FROM yupdates WHERE path = ?",
                        (self.path,),
                    )
                    for update, metadata, timestamp in await cursor.fetchall():
                        if self._decompress:
                            try:
                                update = self._decompress(update)
                            except Exception:
                                pass
                        found = True
                        yield update, metadata, timestamp
                if not found:
                    raise YDocNotFound
        except Exception:
            raise YDocNotFound

    async def write(self, data: bytes) -> None:
        """Store an update.

        Arguments:
            data: The update to store.
        """
        if self.db_initialized is None:
            raise RuntimeError("YStore not started")
        await self.db_initialized.wait()
        async with self.lock:
            async with self._db:
                # first, determine time elapsed since last update
                cursor = await self._db.cursor()
                await cursor.execute(
                    "SELECT timestamp FROM yupdates WHERE path = ? "
                    "ORDER BY timestamp DESC LIMIT 1",
                    (self.path,),
                )
                row = await cursor.fetchone()
                diff = (time.time() - row[0]) if row else 0

                squashed = False
                if self.document_ttl is not None and diff > self.document_ttl:
                    # BEFORE squashing
                    await cursor.execute("SELECT COUNT(*) FROM yupdates WHERE path = ?", (self.path,))
                    before_count = (await cursor.fetchone())[0]
                    if os.path.isfile(self.db_path):
                        file_size_before = os.path.getsize(self.db_path)

                    # squash updates
                    ydoc = Doc()
                    await cursor.execute(
                        "SELECT yupdate FROM yupdates WHERE path = ?",
                        (self.path,),
                    )
                    for (update,) in await cursor.fetchall():
                        if self._decompress:
                            try:
                                update = self._decompress(update)
                            except Exception:
                                pass
                        ydoc.apply_update(update)
                    # delete history
                    await cursor.execute("DELETE FROM yupdates WHERE path = ?", (self.path,))
                    # insert squashed updates
                    squashed_update = ydoc.get_update()
                    compressed_update = (
                        self._compress(squashed_update) if self._compress else squashed_update
                    )
                    metadata = await self.get_metadata()
                    await cursor.execute(
                        "INSERT INTO yupdates VALUES (?, ?, ?, ?)",
                        (self.path, compressed_update, metadata, time.time()),
                    )
                    squashed = True

                    # AFTER squashing
                    await cursor.execute("SELECT COUNT(*) FROM yupdates WHERE path = ?", (self.path,))
                    after_count = (await cursor.fetchone())[0]
                    if os.path.isfile(self.db_path):
                        file_size_after = os.path.getsize(self.db_path)

                # finally, write this update to the DB
                metadata = await self.get_metadata()
                compressed_data = self._compress(data) if self._compress else data
                await cursor.execute(
                    "INSERT INTO yupdates VALUES (?, ?, ?, ?)",
                    (self.path, compressed_data, metadata, time.time()),
                )
                if os.path.isfile(self.db_path):
                    file_size_now = os.path.getsize(self.db_path)

                # storing checkpoints
                self._update_counter += 1
                if self._update_counter >= self.checkpoint_interval:
                    # load or init checkpoint
                    await cursor.execute(
                        "SELECT checkpoint, timestamp FROM ycheckpoints WHERE path = ?",
                        (self.path,),
                    )
                    row = await cursor.fetchone()
                    ydoc = Doc()
                    last_ts = 0.0
                    if row:
                        blob, last_ts = row
                        if self._decompress:
                            try:
                                blob = self._decompress(blob)
                            except Exception:
                                pass
                        ydoc.apply_update(blob)

                    # apply all updates after last_ts
                    await cursor.execute(
                        "SELECT yupdate FROM yupdates "
                        "WHERE path = ? AND timestamp > ? ORDER BY timestamp ASC",
                        (self.path, last_ts),
                    )
                    for (upd,) in await cursor.fetchall():
                        if self._decompress:
                            try:
                                upd = self._decompress(upd)
                            except Exception:
                                pass
                        ydoc.apply_update(upd)

                    # write back the new checkpoint
                    new_ckpt = ydoc.get_update()
                    now = time.time()
                    await cursor.execute(
                        "INSERT OR REPLACE INTO ycheckpoints (path, checkpoint, timestamp) "
                        "VALUES (?, ?, ?)",
                        (self.path, new_ckpt, now),
                    )
                    self._update_counter = 0

class QYStoreMetaclass(type(LoggingConfigurable), type(QStore)):  # type: ignore
    pass

class QYStore(LoggingConfigurable, QStore, metaclass=QYStoreMetaclass):
    db_path = Unicode(
        ".q_ystore.db",
        config=True,
        help="""The path to the YStore database. Defaults to '.q_ystore.db' in the current
        directory.""",
    )

    document_ttl = Int(
        None,
        allow_none=True,
        config=True,
        help="""The document time-to-live in seconds. Defaults to None (document history is never
        cleared).""",
    )

    checkpoint_interval = Int(
        200,
        allow_none=True,
        config=True,
        help="""Interval at which checkpoints are created for efficient document loading""",
    )
