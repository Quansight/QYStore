# q_store

[![Github Actions Status](https://github.com/Quansight/QYStore/workflows/Build/badge.svg)](https://github.com/Quansight/QYStore/blob/main/.github/workflows/build.yml)

# QYStore: A Custom YStore for Jupyter Real-Time Collaboration

`QYStore` is a custom implementation of a YStore for [JupyterLab Collaboration](https://jupyterlab.readthedocs.io/en/stable/user/rtc.html), based on `SQLiteYStore` but with enhanced capabilities such as:

- ✅ In-memory (RAM) database support (`:memory:`)
- ⏳ Document Time-To-Live (TTL)
- 🧠 Automatic checkpointing at regular intervals
- 🗜️ Data compression before saving and decompression after loading
- ⚙️ Configurable via standard Jupyter configuration system

---

## ⚙️ Configuration

By default, when you install this package, the following configuration is automatically set:

```json
{
    "YDocExtension": {
        "ystore_class": "q_store.QYStore"
    },
    "QYStore": {
        "db_path": ":memory:",
        "document_ttl": 10800,
        "checkpoint_interval": 400
    }
}
```

This means:

- The custom `QYStore` class is used as the YStore backend.
- An in-memory SQLite database is used (`db_path: ":memory:"`), so data is not persisted across server restarts.
- Documents are deleted from memory after 3 hours (10,800 seconds) of inactivity.
- A checkpoint is created every 400 updates.

If you need to customize these settings, you can override them in your Jupyter configuration files (e.g., `~/.jupyter/jupyter_server_config.py` or `jupyter_server_config.json`).

For example, to change the TTL or use a persistent database file, update your config as follows:

```python
# Use a persistent SQLite file
c.QYStore.db_path = "qstore.db"

# Set a custom TTL (in seconds)
c.QYStore.document_ttl = 600  # 10 minutes

# Set a custom checkpoint interval
c.QYStore.checkpoint_interval = 100
```

Refer to the [Jupyter documentation](https://jupyterlab.readthedocs.io/en/stable/user/rtc.html) for more details on configuring server extensions.

## 🧪 Features Overview

| Feature               | Description                                                                     |
| --------------------- | ------------------------------------------------------------------------------- |
| `document_ttl`        | Automatically clears documents from memory after a specified time of inactivity |
| `checkpoint_interval` | Automatically saves a checkpoint every N updates to prevent data loss           |
| `db_path`             | Choose between a persistent SQLite file or in-memory database (`:memory:`)      |
| Compression           | Document updates are compressed before storing and decompressed when loading    |

This extension is composed of a Python package named `q_store`
for the server extension and a NPM package named `qStore`
for the frontend extension.

## Requirements

- JupyterLab >= 4.0.0

## Install

To install the extension, execute:

```bash
pip install q_store
```

## Uninstall

To remove the extension, execute:

```bash
pip uninstall q_store
```

## Troubleshoot

If you are seeing the frontend extension, but it is not working, check
that the server extension is enabled:

```bash
jupyter server extension list
```

If the server extension is installed and enabled, but you are not seeing
the frontend extension, check the frontend extension is installed:

```bash
jupyter labextension list
```

## Contributing

### Development install

Note: You will need NodeJS to build the extension package.

The `jlpm` command is JupyterLab's pinned version of
[yarn](https://yarnpkg.com/) that is installed with JupyterLab. You may use
`yarn` or `npm` in lieu of `jlpm` below.

```bash
# Clone the repo to your local environment
# Change directory to the q_store directory
# Install package in development mode
pip install -e "."
# Link your development version of the extension with JupyterLab
jupyter labextension develop . --overwrite
# Server extension must be manually installed in develop mode
jupyter server extension enable q_store
# Rebuild extension Typescript source after making changes
jlpm build
```

You can watch the source directory and run JupyterLab at the same time in different terminals to watch for changes in the extension's source and automatically rebuild the extension.

```bash
# Watch the source directory in one terminal, automatically rebuilding when needed
jlpm watch
# Run JupyterLab in another terminal
jupyter lab
```

With the watch command running, every saved change will immediately be built locally and available in your running JupyterLab. Refresh JupyterLab to load the change in your browser (you may need to wait several seconds for the extension to be rebuilt).

By default, the `jlpm build` command generates the source maps for this extension to make it easier to debug using the browser dev tools. To also generate source maps for the JupyterLab core extensions, you can run the following command:

```bash
jupyter lab build --minimize=False
```

### Development uninstall

```bash
# Server extension must be manually disabled in develop mode
jupyter server extension disable q_store
pip uninstall q_store
```

In development mode, you will also need to remove the symlink created by `jupyter labextension develop`
command. To find its location, you can run `jupyter labextension list` to figure out where the `labextensions`
folder is located. Then you can remove the symlink named `qStore` within that folder.

### Packaging the extension

See [RELEASE](RELEASE.md)
