from jupyter_server.extension.application import ExtensionApp

class QYStoreExtension(ExtensionApp):
    name = "jupyter_qystore"
    app_name = "QYStore"
    description = "Custom YStore extension for JupyterLab RTC"

    def initialize_handlers(self):
        # Inject your custom ystore class into JupyterWebsocketServer
        pass

    def initialize_settings(self):
        # Optional: make the YStore class accessible via server settings
        pass
