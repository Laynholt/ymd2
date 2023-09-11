"""
Copyright 2022 laynholt

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

# Перезапись треков
IS_REWRITABLE = False
# Количество потоков, которые будут обрабатывать один плейлист при загрузке
NUMBER_OF_WORKERS = 5
# Количество треков в одном чанке обработки
CHUNK_OF_TRACKS = 20
# Дебаг мод в логгере
LOGGER_DEBUG_MODE = True

DEFAULT_THEME = 'clam'


# Theme colors
class Color:
    LINK_FG = '#339e29'
    COMBO_DROPLIST_BG_DARK = '#404040'
    COMBO_DROPLIST_BG_LIGHT = '#F8F8F8'


class Actions:
    actions_list = ['d', 'u', 'adb', 'uf']
    actions_list_text_short = ["Скачать", "Обновить", "Добавить в БД", "Обновить"]
    actions_list_text = [
        "Скачать",
        "Обновить метаданные",
        "Добавить в БД без скачивания",
        "Обновить тег любимых в БД для плейлиста"
    ]

    actions_dict = {
        0: 'd',
        1: 'u',
        2: 'adb',
        3: 'uf'
    }

    actions_dict_text = {
        actions_list[0]: "Скачать",
        actions_list[1]: "Обновить метаданные",
        actions_list[2]: "Добавить в БД без скачивания",
        actions_list[3]: "Обновить тег любимых в БД для плейлиста",
    }

    check_actions = {'id': 'cb_id', 'hist': 'cb_history_db', 'rw': 'rewritable'}


paths = {'stuff': 'stuff'}
paths = {
    'dirs': {
        'stuff': f'{paths["stuff"]}',
        'download': 'download',
        'playlists_covers': f'{paths["stuff"]}/playlists_covers',
        'theme': f'{paths["stuff"]}/themes/'
    },

    'files': {
        'history': f'{paths["stuff"]}/history.db',
        'default_playlist_cover': f'{paths["stuff"]}/default_playlist_cover.jpg',
        'favorite_playlist_cover': f'{paths["stuff"]}/favorite_playlist_cover.jpg',
        'icon': f'{paths["stuff"]}/icon.ico',
        'log': f'{paths["stuff"]}/logging.log',
        'config': f'{paths["stuff"]}/config.ini',
        'theme': {
            'dark': 'forest-dark',
            'light': 'forest-light'
        }
    }
}

__version__ = '2.2'
__data__ = '03/2023'
__github__ = 'https://github.com/Laynholt/ymd2'
