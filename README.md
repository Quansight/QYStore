# q_store

[![Github Actions Status](https://github.com/Quansight/QYStore/workflows/Build/badge.svg)](https://github.com/Quansight/QYStore/workflows/build.yml)

# QYStore: A Custom YStore for Jupyter Real-Time Collaboration

`QYStore` is a custom implementation of a YStore for [JupyterLab Collaboration](https://jupyterlab.readthedocs.io/en/stable/user/rtc.html), based on `SQLiteYStore` but with enhanced capabilities such as:

- ✅ In-memory (RAM) database support (`:memory:`)
- ⏳ Document Time-To-Live (TTL)
- 🧠 Automatic checkpointing at regular intervals
- 🗜️ Data compression before saving and decompression after loading
- ⚙️ Configurable via standard Jupyter configuration system

---

## ⚙️ Configuration

To configure your Jupyter Server to use `QYStore`, you need to update your configuration files.

1. Find your Jupyter config directory:

```bash
jupyter --paths
```

2. Edit or create a config file (typically in `~/.jupyter/jupyter_server_config.py`) and add the following lines:

```python
# Use the custom QYStore class
c.YDocExtension.ystore_class = "q_store.QYStore"

# Set the TTL (Time-To-Live) in seconds after which inactive documents are deleted from memory
c.QYStore.document_ttl = 10

# Set the interval (in number of updates) after which checkpoints are created
c.QYStore.checkpoint_interval = 200
```

---

### 🧠 In-Memory (RAM) Database

If you'd like the store to use an in-memory SQLite database (i.e., data is not persisted across server restarts), add the following:

```python
c.QYStore.db_path = ":memory:"
```

This is useful for stateless sessions or ephemeral environments.

---

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
