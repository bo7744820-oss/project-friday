import importlib
import pkgutil
from pathlib import Path


class PluginManager:
    def __init__(self, plugin_folder: Path):
        self.plugin_folder = plugin_folder
        self.plugins = []

    def discover(self):
        if not self.plugin_folder.exists():
            return []
        for importer, name, _ in pkgutil.iter_modules([str(self.plugin_folder)]):
            try:
                module = importlib.import_module(f"modules.{name}")
                self.plugins.append(module)
            except Exception:
                continue
        return self.plugins

    def register(self, plugin):
        self.plugins.append(plugin)

    def list_plugins(self):
        return [getattr(plugin, "__name__", "unknown") for plugin in self.plugins]
