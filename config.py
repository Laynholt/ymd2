"""
Copyright 2023 laynholt

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

# Дебаг мод в логгере
LOGGER_DEBUG_MODE = False
LOGGER_WITHOUT_CONSOLE = False

DEFAULT_THEME = 'clam'


# Theme colors
class Color:
    LINK_FG = '#339e29'
    COMBO_DROPLIST_BG_DARK = '#404040'
    COMBO_DROPLIST_BG_LIGHT = '#F8F8F8'

    DEFAULT_TRACK_COVER1 = '#1e1e2e'
    DEFAULT_TRACK_COVER2 = '#de0052'
    DEFAULT_PLAYLIST_COVER = '#496c88'
    FAVORITE_PLAYLIST_COVER = '#896c4a'


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
        'theme': f'{paths["stuff"]}/themes/',
        'icons': f'{paths["stuff"]}/icons/'
    }
}
paths.update({
    'files': {
        'history': f'{paths["dirs"]["stuff"]}/history.db',
        'default_playlist_cover': f'{paths["dirs"]["icons"]}/default_playlist_cover.png',
        'favorite_playlist_cover': f'{paths["dirs"]["icons"]}/favorite_playlist_cover.png',
        'icon': {
            'main': f'{paths["dirs"]["icons"]}/icon1.ico',
            'info_l': f'{paths["dirs"]["icons"]}/info_64.ico',
            'info_s': f'{paths["dirs"]["icons"]}/info_32.ico',
            'warning_l': f'{paths["dirs"]["icons"]}/warn_64.ico',
            'warning_s': f'{paths["dirs"]["icons"]}/warn_32.ico',
            'error_l': f'{paths["dirs"]["icons"]}/err_64.ico',
            'error_s': f'{paths["dirs"]["icons"]}/err_32.ico',
            'success_l': f'{paths["dirs"]["icons"]}/suc_64.ico',
            'success_s': f'{paths["dirs"]["icons"]}/suc_32.ico',
            },
        'log': f'{paths["dirs"]["stuff"]}/logging.log',
        'config': f'{paths["dirs"]["stuff"]}/config.ini',
        'theme': {
            'dark': 'forest-dark',
            'light': 'forest-light'
        }
    }
})

