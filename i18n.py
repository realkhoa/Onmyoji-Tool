import json
import os
import sys
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal

class I18nManager(QObject):
    language_changed = pyqtSignal(str)

    def __init__(self, locales_dir: str = "locales", default_lang: str = "vi_VN"):
        super().__init__()
        self.locales_dir = Path(locales_dir)
        self.current_lang = default_lang
        self.translations = {}
        self.supported_languages = ["en_US", "vi_VN", "fr_FR", "zh_CN"]
        self.load_language(self.current_lang)

    def load_language(self, lang_code: str):
        if lang_code not in self.supported_languages:
            lang_code = self.supported_languages[0]
            
        file_path = self.locales_dir / f"{lang_code}.json"
        
        # Load from disk if exists, otherwise load empty/fallback
        if getattr(sys, 'frozen', False):
            # If running in PyInstaller bundle
            base_path = Path(sys._MEIPASS)
            file_path = base_path / "locales" / f"{lang_code}.json"
            
        try:
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.translations = json.load(f)
                self.current_lang = lang_code
                self.language_changed.emit(self.current_lang)
                return True
        except Exception as e:
            print(f"Error loading translation file {file_path}: {e}")
            
        self.translations = {}
        return False

    def t(self, key: str, **kwargs) -> str:
        """Translate a key. If not found, returns the key itself."""
        text = self.translations.get(key, key)
        if kwargs:
            try:
                text = text.format(**kwargs)
            except KeyError:
                pass
        return text

# Global singleton
_i18n_instance = None

def get_i18n() -> I18nManager:
    global _i18n_instance
    if _i18n_instance is None:
        _i18n_instance = I18nManager()
    return _i18n_instance

def t(key: str, **kwargs) -> str:
    """Convenience function for translation."""
    return get_i18n().t(key, **kwargs)
