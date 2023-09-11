import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import os
import json
import sqlite3
import asyncio
import threading
import webbrowser
from enum import auto
from strenum import StrEnum
from operator import itemgetter
from queue import Queue
from PIL import Image, ImageTk

import time
import copy

from mutagen import File
from mutagen import id3 as mutag

from yandex_music import Client
from yandex_music.exceptions import YandexMusicError, UnauthorizedError, NetworkError

import config
from libs import utils, session, widgets

import logging.config

logger = logging.getLogger(__name__)
utils.setup_logger(logger, logging.DEBUG if config.LOGGER_DEBUG_MODE else logging.ERROR)


class YandexMusicDownloader:
    def __init__(self):
        self.token = None
        self._history_database_path = None
        self._download_folder_path = None
        self._is_rewritable = None

        self._style = None
        self._style_is_dark_theme = True
        self._style_theme_path = config.paths['dirs']['theme']
        self._style_theme_dark_was_loaded = False
        self._style_theme_light_was_loaded = False
        self._style_theme_file_dark = config.paths['files']['theme']['dark']
        self._style_theme_file_light = config.paths['files']['theme']['light']
        self._style_theme_file = self._style_theme_file_dark if self._style_is_dark_theme else self._style_theme_file_light

        self._style_is_default_theme = False

        self._theme_was_changed = None

    def start(self):
        """
        Метод, для запуска загрузчика

        :return:
        """
        try:
            if self._run_configuration_window():
                self._run_main_window()
        except NetworkError:
            messagebox.showerror('Ошибка', 'Не удалось подключиться к Yandex!\n\nПопробуйте позже.')
        except RuntimeError:
            pass

    def _run_configuration_window(self) -> bool:
        """
        Метод базовой настройки основных пармаетров загрузчика

        :return:
        """
        # Начальная инициализация основных полей
        config_filename = config.paths['files']['config']
        self.token = ''
        self._history_database_path = config.paths['files']['history']
        self._download_folder_path = config.paths['dirs']['download']
        self._is_rewritable = config.IS_REWRITABLE
        self._loop = None

        # Если существует файл конфигурации, то загружаемся с него
        if os.path.exists(config_filename) and os.path.isfile(config_filename):
            try:
                with open(config_filename, 'r', encoding='utf-8') as config_file:
                    try:
                        data = json.load(config_file)
                        self.token = data['token']
                        logger.debug(f'Из файла [{config_filename}] был получен токен: [{self.token}]')
                        self._history_database_path = data['history']
                        logger.debug(
                            f'Из файла [{config_filename}] был получен путь в базе данных: [{self._history_database_path}]')
                        self._download_folder_path = data['download']
                        logger.debug(
                            f'Из файла [{config_filename}] был получен путь к папке загрузок: [{self._download_folder_path}]')
                        self._style_is_default_theme = data['default_theme']
                        logger.debug(f'Значение стандартной темы установлено в: [{self._style_is_default_theme}]')
                        self._style_is_dark_theme = data['dark_theme']
                        logger.debug(f'Значение темной темы установлено в: [{self._style_is_dark_theme}]')
                    except json.decoder.JSONDecodeError:
                        logger.error(f'Ошибка при разборе файла [{config_filename}]!')
                    except KeyError:
                        logger.error(f'Ошибка при попытке извлечь данные. '
                                     f'Видимо файл [{config_filename}] был ошибочно записан, либо некорректно изменён!')
            except IOError:
                logger.error(f'Не удалось открыть файл [{config_filename}] для чтения!')

        _window_configuration = tk.Tk()
        _window_configuration.geometry('625x340')
        try:
            _window_configuration.iconbitmap(config.paths["files"]["icon"])
        except tk.TclError:
            pass

        _window_configuration.title('YMD Конфигурация')
        _window_configuration.resizable(width=False, height=False)

        self._load_theme_styles(_window_configuration)

        _frame_window_configuration = ttk.Frame(_window_configuration)
        _frame_window_configuration.pack(expand=1, fill=tk.BOTH)

        _menu_main = tk.Menu(_frame_window_configuration, tearoff=0)

        _menu_additional = tk.Menu(_menu_main, tearoff=0)
        _is_logger_mode_debug = tk.BooleanVar(value=config.LOGGER_DEBUG_MODE)

        _menu_additional.add_checkbutton(label='Логгер в режиме дебага', onvalue=1, offvalue=0,
                                         variable=_is_logger_mode_debug)

        _menu_themes = tk.Menu(_menu_additional, tearoff=0)

        def _change_to_default(*args):
            self._set_default_theme(menu=_menu_themes)

        _default_theme_var = tk.BooleanVar(value=self._style_is_default_theme)
        _default_theme_var.trace_add('write', _change_to_default)

        _menu_themes.add_checkbutton(label='Простая тема', onvalue=1, offvalue=0, variable=_default_theme_var)

        if self._style_theme_dark_was_loaded and self._style_theme_light_was_loaded:
            self._theme_was_changed = tk.BooleanVar()
            _is_dark_theme = tk.BooleanVar(value=self._style_is_dark_theme)
            _is_dark_theme.trace_add('write', self._change_theme)

            _menu_themes.add_checkbutton(label='Тёмная тема', onvalue=1, offvalue=0, variable=_is_dark_theme)
            if self._style_is_default_theme:
                _menu_themes.entryconfigure('Тёмная тема', state='disabled')
        else:
            _menu_themes.entryconfig('Простая тема', state='disable')
            _window_configuration.geometry('560x320')

        _menu_additional.add_cascade(label='Темы', menu=_menu_themes)
        _menu_main.add_cascade(label='Дополнительно', menu=_menu_additional)

        _separator = ttk.Separator(_frame_window_configuration)
        _separator.pack(pady=5, fill=tk.X)

        _menu_button = ttk.Menubutton(_frame_window_configuration, text='Меню', menu=_menu_main, direction="below")
        _menu_button.pack()

        def _set_logger_level():
            if _is_logger_mode_debug.get():
                logger.setLevel(logging.DEBUG)
            else:
                logger.setLevel(logging.ERROR)

        _frame_required = ttk.Frame(_frame_window_configuration)
        _frame_required.pack(expand=1, fill=tk.BOTH)

        _labelframe_required = ttk.LabelFrame(_frame_required, text='Обязательное заполнение')
        _labelframe_required.grid(column=0, row=0, columnspan=5, rowspan=3, padx=10, pady=10)

        _label_enter_token = ttk.Label(_labelframe_required, text='Введите токен:')
        _label_enter_token.grid(column=0, row=0, padx=5, pady=5)

        _entry_enter_token = ttk.Entry(_labelframe_required, width=68, show="+")
        _entry_enter_token.delete(0, tk.END)
        if len(self.token):
            _entry_enter_token.insert(0, self.token)
        _entry_enter_token.grid(column=1, row=0, columnspan=4, padx=5, pady=5)

        def _change_entry_show_mode():
            show_mode = "+" if _check_state_entry.get() else ""
            _entry_enter_token.config(show=show_mode)

        _check_state_entry = tk.BooleanVar(value=True)
        _checkbox_entry_password = ttk.Checkbutton(_labelframe_required, text='Скрыть токен', var=_check_state_entry,
                                                   command=_change_entry_show_mode)
        _checkbox_entry_password.grid(column=1, row=1, padx=5, pady=5)

        _label_login_password = ttk.Label(_labelframe_required, text='Либо авторизуйтесь через логин и пароль:')
        _label_login_password.grid(column=0, row=2, columnspan=2, padx=5, pady=5)

        # Обработчик гиперссылки
        def _callback(url):
            webbrowser.open_new(url)

        def _authorization():
            """
            Создает окно авторизации

            :return:
            """
            _window_auth = tk.Toplevel(_window_configuration)
            _window_auth.geometry('600x310')
            try:
                _window_auth.iconbitmap(config.paths["files"]["icon"])
            except tk.TclError:
                pass

            _window_auth.title('Окно авторизации')
            _window_auth.resizable(width=False, height=False)

            _frame_window_auth = ttk.Frame(_window_auth)
            _frame_window_auth.pack(expand=1, fill=tk.BOTH)

            _label_info = ttk.Label(_frame_window_auth, text='Вводимые Логин и Пароль нигде не сохраняются и никому '
                                                             'не передаются.\n'
                                                             'Они используюся для авторизации в аккаунте Яндекса и '
                                                             'получение токена,\nкоторый в дальнейшем будет'
                                                             ' использоваться для скачивания медиафалов \nс Вашего аккаунта'
                                                             ' Яндекс Музыки.\n\nВесь исходный код данной программы'
                                                             ' доступен по ссылке на github:',
                                    anchor=tk.CENTER, justify=tk.CENTER)
            _label_info.pack(pady=10)

            _label_github = ttk.Label(_frame_window_auth, text=f'{config.__github__}', foreground=config.Color.LINK_FG,
                                      cursor='hand2')
            _label_github.pack()
            _label_github.bind('<Button-1>', lambda e: _callback(config.__github__))

            _frame_login = ttk.Frame(_frame_window_auth)
            _frame_login.pack(pady=10)

            _label_login = ttk.Label(_frame_login, text='Логин:', width=15, anchor='center')
            _label_login.grid(row=0, column=0, sticky=tk.W)

            _entry_login = ttk.Entry(_frame_login, width=25)
            _entry_login.grid(row=0, column=1, sticky=tk.EW)

            _frame_password = ttk.Frame(_frame_window_auth)
            _frame_password.pack(pady=5)

            _label_password = ttk.Label(_frame_password, text='Пароль:', width=15, anchor='center')
            _label_password.grid(row=1, column=0, sticky=tk.W)

            _entry_password = ttk.Entry(_frame_password, width=25, show="*")
            _entry_password.grid(row=1, column=1, sticky=tk.EW)

            def _change_entry_show_mode1():
                _show_mode = "*" if _check_state_entry1.get() else ""
                _entry_password.config(show=_show_mode)

            _check_state_entry1 = tk.BooleanVar(value=True)
            _checkbox_entry_password1 = ttk.Checkbutton(_frame_window_auth, text='Скрыть пароль',
                                                        var=_check_state_entry1,
                                                        command=_change_entry_show_mode1)
            _checkbox_entry_password1.pack()

            def _auth():
                _set_logger_level()

                login = _entry_login.get()
                if login == '':
                    messagebox.showinfo('Инфо', 'Перед продолжением введите Логин!')
                    return
                password = _entry_password.get()
                if password == '':
                    messagebox.showinfo('Инфо', 'Перед продолжением введите Пароль!')
                    return

                ys = session.YandexSession(login=login, password=password)
                self._loop = asyncio.get_event_loop()
                response = self._loop.run_until_complete(ys.get_music_token())

                # Закрытие лупа перенесено в завершение окна Конфигурации

                if response.get_error() is not None:
                    messagebox.showerror('Ошибка', f'{response.get_error()}')
                    logger.error(f'{response.get_error().replace(chr(10), "")}')
                    return

                if response.get_token() is None:
                    messagebox.showerror('Ошибка', 'Не удалось получить токен!')
                    logger.error('Не удалось получить токен!')
                    return

                self.token = response.get_token()
                _entry_enter_token.delete(0, tk.END)
                _entry_enter_token.insert(0, self.token)
                logger.debug(f'Авторизация прошла успешно! Получен токен для аккаунта [{self.token}].')

                _window_auth.destroy()

            _button_auth = ttk.Button(_frame_window_auth, text='Войти', command=_auth, width=25)
            _button_auth.pack(pady=5)

        _button_login_password = ttk.Button(_labelframe_required, text='Авторизоваться', command=_authorization)
        _button_login_password.grid(column=2, row=2, padx=5, pady=5)

        _label_how_get_token = ttk.Label(_labelframe_required, text='Как получить токен?',
                                         foreground=config.Color.LINK_FG,
                                         cursor='hand2')
        _label_how_get_token.grid(column=4, row=1, sticky=tk.E, padx=5, pady=5)

        _label_how_get_token.bind('<Button-1>', lambda e: _callback("https://github.com/MarshalX/yandex-music-api/"
                                                                    "discussions/513#discussioncomment-2729781"))

        _labelframe_optional = ttk.LabelFrame(_frame_required, text='Опциональное заполнение')
        _labelframe_optional.grid(column=0, row=3, columnspan=5, rowspan=2, padx=10, pady=10)

        # Выбираем файл базы данных
        def _choose_database():
            database = filedialog.askopenfilename(
                title="Укажите файл базы данных",
                filetypes=[("Все файлы", "*.db*")]
            )
            if database != "":
                self._history_database_path = os.path.abspath(database)
            _set_logger_level()
            logger.debug(f'Файл базы данных установлен на: [{self._history_database_path}].')

        _button_history = ttk.Button(_labelframe_optional, text='Указать БД', command=_choose_database)
        _button_history.grid(column=0, row=3, padx=5, pady=5)

        # Выбираем папку, куда качать
        def _choose_download():
            folder = filedialog.askdirectory(title="Выберете папку Загрузки")
            if folder != "":
                self._download_folder_path = os.path.abspath(folder)
            _set_logger_level()
            logger.debug(f'Папка загрузки установлена на: [{self._download_folder_path}].')

        _button_download = ttk.Button(_labelframe_optional, text='Указать папку Download', command=_choose_download)
        _button_download.grid(column=1, row=3, padx=5, pady=5)

        _check_is_rewritable = tk.BooleanVar(value=self._is_rewritable)
        _checkbox_rewritable = ttk.Checkbutton(_labelframe_optional, text='Перезаписывать существующие композиции',
                                               var=_check_is_rewritable)
        _checkbox_rewritable.grid(column=2, row=3, padx=5, pady=5)

        # Экшен, для установки значений по умолчанию
        def _reset_all():
            self.token = ''
            _entry_enter_token.delete(0, tk.END)
            self._history_database_path = config.paths['files']['history']
            self._download_folder_path = config.paths['dirs']['download']
            _set_logger_level()
            logger.debug(f'Токен установлен в [{self.token}].')
            logger.debug(f'Путь к файлу базы данных установлен в [{self._history_database_path}].')
            logger.debug(f'Путь к папке Загрузки установлен в [{self._download_folder_path}].')
            _check_is_rewritable.set(self._is_rewritable)

        _button_reset = ttk.Button(_frame_required, text='Сбросить всё', command=_reset_all)
        _button_reset.grid(column=0, row=5, padx=10, pady=5, sticky=tk.W)

        is_continue = False

        # Экшен, для перехода на главное окно приложения
        def _continue_action():
            if _entry_enter_token.get() == '':
                messagebox.showinfo('Инфо', 'Перед продолжением необходимо ввести токен!')
                return
            self.token = _entry_enter_token.get()
            self._is_rewritable = _check_is_rewritable.get()

            _set_logger_level()
            try:
                with open(config_filename, 'w', encoding='utf-8') as config_file1:
                    data1 = {
                        'token': self.token,
                        'history': self._history_database_path,
                        'download': self._download_folder_path,
                        'default_theme': self._style_is_default_theme,
                        'dark_theme': self._style_is_dark_theme
                    }
                    json.dump(data1, config_file1)
                    logger.debug(
                        f'Значения токена: [{self.token}], пути к базе данных: [{self._history_database_path}] '
                        f'и пути к папке скачивания: [{self._download_folder_path}] были записаны в файл: '
                        f'[{config_filename}].')
            except IOError:
                logger.error(f'Не удалось открыть файл [{config_filename}] для записи!')
            nonlocal is_continue
            is_continue = True
            _window_configuration.destroy()

        _button_continue = ttk.Button(_frame_required, text='Продолжить', command=_continue_action)
        _button_continue.grid(column=4, row=5, padx=10, pady=5, sticky=tk.E)

        _window_configuration.mainloop()

        # Если мы вводили логин и пароль, то у нас весит сессия, которую нужно закрыть, иначе будет зомби поток,
        # который помешает завершить корректно программу в дальнейшем
        if self._loop is not None:
            # Слип для закрытия соединения
            # https://docs.aiohttp.org/en/stable/client_advanced.html#graceful-shutdown
            self._loop.run_until_complete(asyncio.sleep(1))
            self._loop.close()

        return is_continue

    def _load_theme_styles(self, window):
        if os.path.exists(f'{self._style_theme_path}{self._style_theme_file}.tcl'):
            try:
                window.tk.call("source", f'{self._style_theme_path}{self._style_theme_file_dark}.tcl')
                self._style_theme_dark_was_loaded = True
            except tk.TclError:
                logger.error(f'Ошибка при открытии файла [{self._style_theme_path}{self._style_theme_file_dark}.tcl]!')
            try:
                window.tk.call("source", f'{self._style_theme_path}{self._style_theme_file_light}.tcl')
                self._style_theme_light_was_loaded = True
            except tk.TclError:
                logger.error(f'Ошибка при открытии файла [{self._style_theme_path}{self._style_theme_file_light}.tcl]!')
            try:
                self._style = ttk.Style(window)
                self._style_theme_file = self._style_theme_file_dark if self._style_is_dark_theme else self._style_theme_file_light
                self._style.theme_use(self._style_theme_file if not self._style_is_default_theme else config.DEFAULT_THEME)
            except tk.TclError:
                logger.error(f'Не удалось установить стиль [{self._style_theme_file}]!')
        else:
            self._style = ttk.Style(window)
            self._style.theme_use(config.DEFAULT_THEME)

    def _change_theme(self, *args):
        if self._style_theme_dark_was_loaded and self._style_theme_light_was_loaded:
            self._style_is_dark_theme = not self._style_is_dark_theme
            self._style_theme_file = self._style_theme_file_dark if self._style_is_dark_theme else self._style_theme_file_light
            self._style.theme_use(self._style_theme_file)

            self._theme_was_changed.set(self._style_is_dark_theme)

    def _set_default_theme(self, menu):
        self._style_is_default_theme = not self._style_is_default_theme

        if self._style_is_default_theme is True:
            self._style.theme_use(config.DEFAULT_THEME)

            # Отключаем переключатель у темной/светлой
            if self._style_theme_dark_was_loaded and self._style_theme_light_was_loaded:
                menu.entryconfigure('Тёмная тема', state='disabled')
        else:
            if self._style_theme_dark_was_loaded and self._style_theme_light_was_loaded:
                menu.entryconfigure('Тёмная тема', state='active')
                self._style_theme_file = self._style_theme_file_dark if self._style_is_dark_theme else self._style_theme_file_light
                self._style.theme_use(self._style_theme_file)

                self._theme_was_changed.set(self._style_is_dark_theme)

    def _run_main_window(self):
        """
        Метод работы основного окна

        :return:
        """
        self._window_main = tk.Tk()
        self._window_main.geometry('610x220')
        try:
            self._window_main.iconbitmap(config.paths["files"]["icon"])
        except tk.TclError:
            pass

        self._window_main.title('YMD')
        self._window_main.resizable(width=False, height=False)

        self._load_theme_styles(self._window_main)

        # Создаем окно загрузок
        self._window_download = tk.Toplevel(self._window_main)
        self._window_download.withdraw()
        self._window_download.geometry('610x400')
        self._window_download.title('YMD Загрузки')
        self._window_download.minsize(width=670, height=400)
        self._window_download.protocol("WM_DELETE_WINDOW", lambda: self._window_download.withdraw())

        self._frame_download_main = ttk.Frame(self._window_download)
        self._frame_download_main.pack(expand=1, fill=tk.BOTH)

        self._notebook_download = ttk.Notebook(self._frame_download_main)
        self._notebook_download.pack(padx=5, pady=5, expand=1, fill=tk.BOTH)

        self._init_downloader()

        # Меню
        def _about():
            about_window = tk.Toplevel(self._window_main)
            about_window.geometry('250x90')
            about_window.title('О программе')
            try:
                about_window.iconbitmap(config.paths["files"]["icon"])
            except tk.TclError:
                pass
            about_window.resizable(width=False, height=False)

            frame_window_about = ttk.Frame(about_window)
            frame_window_about.pack(expand=1, fill=tk.BOTH)

            label_about = ttk.Label(frame_window_about, text=f'Версия: {config.__version__};\n'
                                                             f'Написал laynholt в {config.__data__};\n'
                                                             f'Репозиторий:', justify=tk.CENTER)
            label_about.pack(padx=5, pady=5)

            label_git = ttk.Label(frame_window_about, text=f'{config.__github__}',
                                  foreground=config.Color.LINK_FG,
                                  cursor='hand2', justify=tk.CENTER)
            label_git.pack(padx=5)

            # Обработчик гиперссылки
            def _callback(url):
                webbrowser.open_new(url)

            label_git.bind('<Button-1>', lambda e: _callback(config.__github__))

        self._frame_window_main = ttk.Frame(self._window_main)
        self._frame_window_main.pack(expand=1, fill=tk.BOTH)

        self._menu_main = tk.Menu(self._frame_window_main, tearoff=0)

        self._menu_help = tk.Menu(self._menu_main, tearoff=0)
        self._menu_help.add_command(label='О программе', command=_about)

        self._menu_additional = tk.Menu(self._menu_main, tearoff=0)
        self._menu_additional.add_command(label='Расширенная загрузка', command=lambda: self._extend_downloading())
        self._menu_additional.add_command(label='Окно загрузок', command=lambda: self._window_download.deiconify())

        self._menu_themes = tk.Menu(self._menu_additional, tearoff=0)

        def _change_to_default(*args):
            self._set_default_theme(menu=self._menu_themes)

        _default_theme_var = tk.BooleanVar(value=self._style_is_default_theme)
        _default_theme_var.trace_add('write', _change_to_default)

        self._menu_themes.add_checkbutton(label='Простая тема', onvalue=1, offvalue=0, variable=_default_theme_var)

        self._is_dark_theme = None
        if self._style_theme_dark_was_loaded and self._style_theme_light_was_loaded:
            self._is_dark_theme = tk.BooleanVar(value=self._style_is_dark_theme)
            self._is_dark_theme.trace_add('write', self._change_theme)

            self._menu_themes.add_checkbutton(label='Тёмная тема', onvalue=1, offvalue=0, variable=self._is_dark_theme)
            if self._style_is_default_theme:
                self._menu_themes.entryconfigure('Тёмная тема', state='disabled')
        else:
            self._menu_themes.entryconfig('Простая тема', state='disable')
            self._window_main.geometry('540x220')

        self._menu_additional.add_cascade(label='Темы', menu=self._menu_themes)
        self._menu_main.add_cascade(label='Дополнительно', menu=self._menu_additional)
        self._menu_main.add_cascade(label='Справка', menu=self._menu_help)

        _separator = ttk.Separator(self._frame_window_main)
        _separator.pack(pady=5, fill=tk.BOTH)

        self._menu_button = ttk.Menubutton(self._frame_window_main, text='Меню', menu=self._menu_main,
                                           direction="below")
        self._menu_button.pack()

        self._frame_main = ttk.Frame(self._frame_window_main)
        self._frame_main.pack(pady=10, expand=1, fill=tk.BOTH)

        current_playlist_cover = ImageTk.PhotoImage(Image.open(config.paths['files']['default_playlist_cover']))
        self._label_playlist_cover = ttk.Label(self._frame_main, image=current_playlist_cover)
        self._label_playlist_cover.grid(column=0, row=0, rowspan=3, sticky=tk.W, padx=22, pady=5)

        _label_playlist_names = ttk.Label(self._frame_main, text='Выберете плейлист для скачивания:')
        _label_playlist_names.grid(column=1, row=0, columnspan=2, sticky=tk.W, pady=5)

        # Реагируем на изменения в комбобоксе и вызываем метод отбновления обложки
        def _combo_was_updated(value=None):
            self._change_current_playlist_cover()
            return True

        self._combo_playlists = widgets.JustifiedCombobox(self._frame_main, state='readonly',
                                                          width=40, validate='focusout',
                                                          justify=tk.CENTER,
                                                          validatecommand=(
                                                              self._window_main.register(_combo_was_updated), '%P'))
        self._combo_playlists.grid(column=1, row=1, columnspan=2, sticky=tk.W)
        self._combo_playlists.bind('<<ComboboxSelected>>', _combo_was_updated)

        self._label_track_number_text = ttk.Label(self._frame_main, text='Количество треков в плейлисте:')
        self._label_track_number_text.grid(column=1, row=2, columnspan=2, sticky=tk.W, pady=5)

        self._check_state_history = tk.BooleanVar(value=True)
        self._checkbox_history = ttk.Checkbutton(self._frame_main, text='Скачать только новые треки (нужна history.db)',
                                                 var=self._check_state_history)
        self._checkbox_history.grid(column=0, row=3, columnspan=3, sticky=tk.W, padx=22)

        def _download():
            _thread = threading.Thread(target=self._simple_downloading, daemon=True)
            _thread.start()

        self._button_download = ttk.Button(self._frame_main, width=15, text='Скачать', command=_download)
        self._button_download.grid(column=3, row=3)

        # Изменяем правило, при закрытие окна
        def _prepare_to_close_main_program():
            # self._window_main.event_generate(f'<<{self.Events.MAIN_WINDOW_CLOSE}>>')

            logger.debug('Идет завершение программы...')

            main_thread = threading.current_thread()
            alive_threads = threading.enumerate()
            for _thread in alive_threads:
                if _thread is main_thread:
                    logger.debug(f'Основной поток [{main_thread.ident}] ожидает завершения всех дочерних.')
                    continue
                if not _thread.isDaemon():
                    _thread_id = _thread.ident
                    logger.debug(f'Ожидание заверешния потока [{_thread_id}]')
                    _thread.join()
                    logger.debug(f'Поток [{_thread_id}] был завершён.')
            logger.debug('Все потоки завершены. Завершение основного потока...')
            self._window_main.destroy()

        self._window_main.protocol("WM_DELETE_WINDOW", _prepare_to_close_main_program)
        self._window_main.mainloop()

    def _init_downloader(self):
        """
        Инициализвания загрузчика

        :return:
        """
        self._playlists_covers_folder_name = config.paths['dirs']['playlists_covers']

        self._window_child_extend_downloading = None

        self._window_main.bind(f'<<{self.Events.PLAYLISTS_INFO_LOADED}>>', self._analyze_updated_playlist_info)
        self._window_main.bind(f'<<{self.Events.COVERS_LOADED}>>', self._change_current_playlist_cover)

        self._wrapper = self.DownloaderWrapper(token=self.token,
                                               _history_database_path=self._history_database_path,
                                               _download_folder_path=self._download_folder_path,
                                               _playlists_covers_folder_name=self._playlists_covers_folder_name,
                                               _is_rewritable=self._is_rewritable,
                                               _event=self._window_main,
                                               _create_download_instance=self._create_new_download_instance)
        # Загружаем все пользовательские данные
        thread = threading.Thread(target=self._wrapper.init, daemon=True)
        thread.start()

        # Создаем нужные директории
        self._create_stuff_directories()

    def _create_stuff_directories(self):
        """
        Создаём нужны директории для работы:
            1) Директорию для дефолтной обложки плейлиста и её, если нет
            2) Директорию, где будем хранить все обложки плейлистов

        :return:
        """
        # Если нет дефолного изображения альбома, то создаем его
        default_playlist_cover = config.paths['files']['default_playlist_cover']
        if not os.path.exists(default_playlist_cover):
            default_img = Image.new('RGB', (100, 100), color=(73, 109, 137))

            stuff_directory = config.paths['dirs']['stuff']
            if not os.path.exists(stuff_directory) or os.path.isfile(stuff_directory):
                os.makedirs(stuff_directory, exist_ok=True)
                logger.debug(f'Служебная директория была содана по пути [{stuff_directory}].')
            default_img.save(default_playlist_cover)
            logger.debug(f'Дефолтная обложка не была найдена, поэтому была создана занова и сохранена по пути '
                         f'[{default_playlist_cover}]!')

        favorite_playlist_cover = config.paths['files']['favorite_playlist_cover']
        if not os.path.exists(favorite_playlist_cover):
            img = Image.new('RGB', (100, 100), color=(137, 109, 73))
            img.save(favorite_playlist_cover)
            logger.debug(
                f'Обложка для альбому Любимое не была найдена, поэтому была создана занова и сохранена по пути '
                f'[{favorite_playlist_cover}]!')

        # Если папки с обложками не существует, то создаем
        if not os.path.exists(self._playlists_covers_folder_name) or os.path.isfile(self._playlists_covers_folder_name):
            os.makedirs(self._playlists_covers_folder_name, exist_ok=True)
            logger.debug(f'Была создана папка [{self._playlists_covers_folder_name}] для хранения обложек плейлистов.')
        else:
            logger.debug('Папка для обложек уже сущестует.')

    def _change_current_playlist_cover(self, *args):
        """
        Меняем отображающуюся текущую обложку плейлиста
        :return:
        """
        current_playlist_index = self._combo_playlists.current()
        if current_playlist_index == -1:
            logger.debug('Список плейлистов пуст, поэтому не удалось изменить обложку.')
            return

        current_playlist = self._wrapper.playlists[current_playlist_index]
        playlist_title = utils.strip_bad_symbols(current_playlist.title)

        if current_playlist.kind != 3:
            filename = config.paths['files']['default_playlist_cover']
        else:
            filename = config.paths['files']['favorite_playlist_cover']
        try:
            if current_playlist.cover:
                if current_playlist.cover.items_uri is not None:
                    if not os.path.exists(f'{self._playlists_covers_folder_name}/{playlist_title}.jpg'):
                        logger.debug(f'Обложка для плейлиста [{playlist_title}] не была найдена, начинаю загрузку.')
                        current_playlist.cover.download(
                            filename=f'{self._playlists_covers_folder_name}/{playlist_title}.jpg',
                            size='100x100')
                        logger.debug(f'Обложка для плейлиста [{playlist_title}] была загружена в '
                                     f'[{self._playlists_covers_folder_name}/{playlist_title}.jpg].')
                    filename = f'{self._playlists_covers_folder_name}/{playlist_title}.jpg'
        except NetworkError:
            logger.error('Не удалось подключиться к Yandex!')

        current_playlist_cover = ImageTk.PhotoImage(Image.open(filename))
        self._label_playlist_cover.configure(image=current_playlist_cover)
        self._label_playlist_cover.image = current_playlist_cover

        text = self._label_track_number_text['text'].split(':')[0]
        self._label_track_number_text.config(text=f'{text}: {current_playlist.track_count}')
        logger.debug(f'Текущая обложка изменена на [{playlist_title}].')

    def _database_create_tables(self):
        """
        Создаем необходмые таблицы в базе данных, если их ещё нет
        :return:
        """
        with sqlite3.connect(self._history_database_path) as db:
            logger.debug(f'База данных по пути [{self._history_database_path}] была открыта.')
            for playlist in self._wrapper.playlists:
                playlist_title = utils.strip_bad_symbols(playlist.title).replace(' ', '_')
                cur = db.cursor()
                request = f"CREATE TABLE IF NOT EXISTS table_{playlist_title}(" \
                          f"track_id INTEGER NOT NULL," \
                          f"artist_id TEXT NOT NULL," \
                          f"album_id TEXT," \
                          f"track_name TEXT NOT NULL," \
                          f"artist_name TEXT NOT NULL," \
                          f"album_name TEXT," \
                          f"genre TEXT," \
                          f"track_number INTEGER NOT NULL," \
                          f"disk_number INTEGER NOT NULL," \
                          f"year INTEGER," \
                          f"release_data TEXT," \
                          f"bit_rate INTEGER NOT NULL," \
                          f"codec TEXT NOT NULL," \
                          f"is_favorite INTEGER NOT NULL," \
                          f"is_explicit INTEGER NOT NULL DEFAULT 0," \
                          f"is_popular INTEGER NOT NULL DEFAULT 0" \
                          f")"
                cur.execute(request)

    def _analyze_updated_playlist_info(self, *args):
        # Создание необходимых таблиц в базе данных
        thread = threading.Thread(target=self._database_create_tables, daemon=True)
        thread.start()

        # Обновляем значения комбобокса
        self._fill_combo_values()

    def _fill_combo_values(self):
        if self._wrapper.wrapper_state_is_ok:
            # Заполняем комбо названиями плейлистов
            for playlist in self._wrapper.playlists:
                self._combo_playlists['values'] = (*self._combo_playlists['values'], f'{playlist.title}')
            self._combo_playlists.current(0)

            # Изменияем текущую отображающуюся обложку плейлиста
            self._change_current_playlist_cover()

    def _simple_downloading(self):
        if self._combo_playlists.current() == -1:
            return

        # Формируем датафрейм для дальнейшей отправки его в загрузчик

        data_frame = {'d': {}, config.Actions.check_actions['id']: False,
                      config.Actions.check_actions['rw']: self._is_rewritable,
                      config.Actions.check_actions['hist']: self._check_state_history.get()}

        playlist = self._wrapper.playlists[self._combo_playlists.current()]
        if playlist.kind not in self._wrapper.marked_up_data:
            # Если данных о текущем плейлисте нет, то скачиваем их
            self._wrapper.data_markup(playlist.kind)

        # Формируем датафрейм
        data_frame['d'][playlist.kind] = self._wrapper.marked_up_data[playlist.kind]

        self._wrapper.basket_queue.put(data_frame)
        self._window_main.event_generate(f'<<{self.Events.CHECK_BASKET_QUEUE}>>')

    def _extend_downloading(self):
        if self._window_child_extend_downloading is not None or not self._wrapper.wrapper_state_is_ok:
            return

        self._window_child_extend_downloading = tk.Toplevel(self._window_main)
        self._window_child_extend_downloading.geometry("950x700")
        self._window_child_extend_downloading.minsize(950, 700)
        self._window_child_extend_downloading.title('YMD Расширенная загрузка')
        try:
            self._window_child_extend_downloading.iconbitmap(config.paths["files"]["icon"])
        except tk.TclError:
            pass

        def _prepare_to_close():
            self._window_child_extend_downloading.destroy()
            self._window_child_extend_downloading = None

        def _dont_close():
            pass

        self._window_child_extend_downloading.protocol("WM_DELETE_WINDOW", _prepare_to_close)

        # Блок загрузки данных о треках

        def _load_playlist_data_to_tree_view1(*args):
            """
            Отображаем данные плейлистов в TreeView1

            :param args:
            :return:
            """

            try:
                playlist_index = self._wrapper.playlists[_combobox_playlists.current()].kind
                title_pattern = _entry_string_variable.get()

                # Данные текущего плейлиста сейчас заполняются, выходим
                if playlist_index in self._wrapper.playlists_are_marking_up:
                    return

                if playlist_index not in self._wrapper.marked_up_data:
                    _thread1 = threading.Thread(target=self._wrapper.data_markup, args=[playlist_index, _thread_event],
                                                daemon=True)
                    _thread1.start()
                    return

                # Очищаем предыдущие данные
                _tree_view_tab1.tv_delete()

                tree_view1_data = []
                # Формируем данные для TreeView для текущего плейлиста
                for track_info in self._wrapper.marked_up_data[playlist_index]:
                    if title_pattern.lower() in track_info['title'].lower() or \
                            title_pattern.lower() in track_info['artists'].lower() or \
                            title_pattern.lower() in track_info['albums'].lower():
                        tree_view1_data.append([
                            track_info['title'],
                            track_info['artists'],
                            track_info['albums']
                        ])

                tree_view1_data = sorted(tree_view1_data, key=itemgetter(0))

                # Заполняем TreeView для текущего плейлиста
                count = 0
                for item in tree_view1_data:
                    _tree_view_tab1.tv_insert(parent='', index='end', iid=count, text='', values=item)
                    count += 1

            except tk.TclError:
                pass

        basket = {}

        def _load_playlist_data_to_tree_view2():
            """
            Отображаем данные плейлистов в TreeView2 (корзине)

            :return:
            """
            try:
                title_pattern = _entry_string_variable.get()
                action_index = _combobox_action_type.current()

                # Очищаем предыдущие данные
                _tree_view_tab2.tv_delete()

                tree_view2_data = []
                # Формируем данные для TreeView2
                for action_type, playlists in basket.items():
                    if action_type == config.Actions.actions_dict[action_index]:
                        for playlist_kind, playlist_data in playlists.items():
                            old_size = len(tree_view2_data)

                            for playlist_value in playlist_data:
                                if title_pattern.lower() in playlist_value[1].lower() or \
                                        title_pattern.lower() in playlist_value[2].lower() or \
                                        title_pattern.lower() in playlist_value[3].lower():
                                    tree_view2_data.append(playlist_value)

                            # Если из плейлиста была добавлена композиция, то добавляем и название плейлиста
                            if len(tree_view2_data) != old_size:
                                if playlist_data[0] not in tree_view2_data:
                                    tree_view2_data.insert(old_size, playlist_data[0])

                # Заполняем TreeView2
                count = 0
                parent = ''
                for playlist_value in tree_view2_data:
                    if playlist_value[0]:
                        parent = ''
                    _tree_view_tab2.tv_insert(parent=parent, index='end', iid=count, text=playlist_value[0],
                                              values=playlist_value[1:])
                    if playlist_value[0]:
                        parent = count
                    count += 1

                _tree_view_tab2.tv_open()

            except tk.TclError:
                pass

        def _add_playlist_to_basket():
            """
            Добавляем текущий плейлист в корзину

            :return:
            """

            playlist_index = self._wrapper.playlists[_combobox_playlists.current()].kind
            action_index = config.Actions.actions_dict[_combobox_action_type.current()]

            # Данные текущего плейлиста сейчас заполняются, выходим
            if playlist_index in self._wrapper.playlists_are_marking_up:
                messagebox.showinfo('Инфо', 'Подождите, данные текущего плейлиста сейчас заполняются.',
                                    parent=self._window_child_extend_downloading)
                return

            _basket = []

            # Добавляем инфу о композициях
            for track_info in self._wrapper.marked_up_data[playlist_index]:
                _basket.append([
                    '',
                    track_info['title'],
                    track_info['artists'],
                    track_info['albums']
                ])

            if action_index not in basket:
                basket.update({action_index: {}})

            basket[action_index][playlist_index] = sorted(_basket, key=itemgetter(1))

            # Добавляем строку плейлиста
            basket[action_index][playlist_index].insert(0, [_combobox_playlists.get(), '', '', ''])

            # Обновляем окно корзины
            _load_playlist_data_to_tree_view2()

            if _button_download_all_allow_states[_combobox_action_type.current()] is True:
                _button_download_selected['state'] = 'normal'
                _button_download_selected_allow_states[_combobox_action_type.current()] = True

        def _add_partial_playlist_to_basket():
            """
            Добавляем текущий плейлист с выбранными композициями в корзину

            :return:
            """

            playlist_index = self._wrapper.playlists[_combobox_playlists.current()].kind
            action_index = config.Actions.actions_dict[_combobox_action_type.current()]

            # Данные текущего плейлиста сейчас заполняются, выходим
            if playlist_index in self._wrapper.playlists_are_marking_up:
                messagebox.showinfo('Инфо', 'Подождите, данные текущего плейлиста сейчас заполняются.',
                                    parent=self._window_child_extend_downloading)
                return

            selected_items = [[''] + list(item) for item in _tree_view_tab1.tv_get_multi_selected(option='values')]

            if selected_items:
                # Для данного экшена
                if action_index in basket:
                    # Если в корзине уже есть какая-то часть данного плейлиста
                    if playlist_index in basket[action_index]:
                        old_size = len(basket[action_index][playlist_index])

                        for item in selected_items:
                            if item not in basket[action_index][playlist_index]:
                                basket[action_index][playlist_index].append(item)

                        # Добавили какие-то новые композиции, значит надо отсортировать
                        if len(basket[action_index][playlist_index]) != old_size:
                            # Удаляем строку о плейлисте
                            basket[action_index][playlist_index].remove(basket[action_index][playlist_index][0])

                            basket[action_index][playlist_index] = sorted(basket[action_index][playlist_index],
                                                                          key=itemgetter(1))

                            # Добавляем строку плейлиста
                            basket[action_index][playlist_index].insert(0, [_combobox_playlists.get(), '', '', ''])
                        else:
                            return

                    # Если данный экшен есть в корзине, но нет плейлиста
                    else:
                        basket[action_index][playlist_index] = sorted(selected_items, key=itemgetter(1))

                        # Добавляем строку плейлиста
                        basket[action_index][playlist_index].insert(0, [_combobox_playlists.get(), '', '', ''])

                # Иначе добавляем этот экшен в корзину
                else:
                    basket.update({action_index: {}})
                    basket[action_index][playlist_index] = sorted(selected_items, key=itemgetter(1))

                    # Добавляем строку плейлиста
                    basket[action_index][playlist_index].insert(0, [_combobox_playlists.get(), '', '', ''])

                # Обновляем окно корзины
                _load_playlist_data_to_tree_view2()

                if _button_download_all_allow_states[_combobox_action_type.current()] is True:
                    _button_download_selected['state'] = 'normal'
                    _button_download_selected_allow_states[_combobox_action_type.current()] = True

        def _delete_playlist_from_basket():
            """
            Удаляет текущий плейлист из корзины

            :return:
            """
            playlist_index_combo = self._wrapper.playlists[_combobox_playlists.current()].kind
            playlist_index_selected = None
            action_index = config.Actions.actions_dict[_combobox_action_type.current()]

            selected_text = _tree_view_tab2.tv_get_selected(option='text')
            if selected_text:
                combo_index = _combobox_playlists['values'].index(selected_text)
                playlist_index_selected = self._wrapper.playlists[combo_index].kind

            playlist_index = playlist_index_combo if playlist_index_selected is None else playlist_index_selected

            if playlist_index in basket[action_index]:
                del basket[action_index][playlist_index]
                if not basket[action_index]:
                    del basket[action_index]

                # Обновляем окно корзины
                _load_playlist_data_to_tree_view2()

        def _delete_partial_playlist_from_basket():
            """
            Удаляет выбранные композиции текущего плейлиста из корзины

            :return:
            """
            action_index = config.Actions.actions_dict[_combobox_action_type.current()]

            parent_texts = _tree_view_tab2.tv_get_parent_of_selected()
            if parent_texts:
                combo_indexes = [_combobox_playlists['values'].index(parent_text) for parent_text in parent_texts]
                playlist_indexes = [self._wrapper.playlists[combo_index].kind for combo_index in combo_indexes]

                selected_texts = _tree_view_tab2.tv_get_multi_selected(option='text')
                selected_values = _tree_view_tab2.tv_get_multi_selected(option='values')
                selected_items = []
                for i in range(len(selected_texts)):
                    selected_items.append(['' + selected_texts[i]] + list(selected_values[i]))

                for playlist_index in playlist_indexes:
                    for item in selected_items:
                        # Если композиция есть в корзине и это не название плейлиста
                        if item in basket[action_index][playlist_index] and not item[0]:
                            basket[action_index][playlist_index].remove(item)

                    # Если композиций в корзине у плейлиста не осталось, то удаляем его название
                    if len(basket[action_index][playlist_index]) == 1:
                        del basket[action_index][playlist_index]

                        # Если других плейлистов тоже не осталось, то удаляем экшен
                        if not basket[action_index]:
                            del basket[action_index]

                # Обновляем окно корзины
                _load_playlist_data_to_tree_view2()

        def _entry_was_changed(*args):
            notebook_index = _notebook.index(_notebook.select())
            if not notebook_index:
                _load_playlist_data_to_tree_view1()
            else:
                _load_playlist_data_to_tree_view2()

        def _combo_playlists_was_updated(value):
            _load_playlist_data_to_tree_view1()

        def _combo_action_was_updated(value):
            _current_action_text1 = config.Actions.actions_list_text_short[_combobox_action_type.current()]
            _button_download_all['text'] = f'{_current_action_text1}{_button_download_all_postfix_text}'
            _button_download_selected['text'] = f'{_current_action_text1}{_button_download_selected_postfix_text}'

            _button_download_all['state'] = 'normal' \
                if _button_download_all_allow_states[_combobox_action_type.current()] is True else 'disable'
            _button_download_selected['state'] = 'normal' \
                if _button_download_selected_allow_states[_combobox_action_type.current()] is True else 'disable'

            _load_playlist_data_to_tree_view2()

        def _clear_basket():
            basket.clear()
            _entry_was_changed()

        def _prepare_to_download(partial_mode=True):
            current_action = config.Actions.actions_dict[_combobox_action_type.current()]
            if partial_mode:
                if current_action not in basket:
                    messagebox.showinfo('Инфо', 'Сначала добавьте нужные композиции в корзину!',
                                        parent=self._window_child_extend_downloading)
                    return
                _thread_prepare = threading.Thread(target=_preparing_to_partial_download, daemon=True)
            else:
                _thread_prepare = threading.Thread(target=_preparing_to_full_download, daemon=True)
                _button_download_all['state'] = 'disabled'
                _button_download_all_allow_states[_combobox_action_type.current()] = False

            _button_download_selected['state'] = 'disabled'
            _button_download_selected_allow_states[_combobox_action_type.current()] = False

            self._window_child_extend_downloading.protocol("WM_DELETE_WINDOW", _dont_close)

            _thread_prepare.start()
            if not partial_mode:
                messagebox.showinfo('Инфо',
                                    'Подождите, идет формирование дейтограммы для плейлистов.\nЗагрузка скоро начнется.',
                                    parent=self._window_child_extend_downloading)

        def _preparing_to_partial_download():
            action_type = config.Actions.actions_dict[_combobox_action_type.current()]
            data_frame = {action_type: {}, config.Actions.check_actions['id']: self._check_add_ids.get(),
                          config.Actions.check_actions['rw']: self._check_rewritable.get(),
                          config.Actions.check_actions['hist']: self._check_state_history.get()}

            # Переносим все плейлисты из корзины с текущим экшеном в датафрейм
            # Формируем датафрейм
            for playlist_kind, basket_playlist_data in basket[action_type].items():

                playlist_data = []
                # Ищем текущие данные в размеченных данных
                for playlist_value in self._wrapper.marked_up_data[playlist_kind]:
                    for basket_playlist_value in basket_playlist_data:
                        if playlist_value['title'] in basket_playlist_value[1] and \
                                playlist_value['artists'] in basket_playlist_value[2] and \
                                playlist_value['albums'] in basket_playlist_value[3]:
                            playlist_data.append(playlist_value)
                data_frame[action_type][playlist_kind] = playlist_data

            # Отчищаем всё из корзины для текущего экшена
            del basket[action_type]

            _load_playlist_data_to_tree_view2()

            self._wrapper.basket_queue.put(data_frame)
            self._window_main.event_generate(f'<<{self.Events.CHECK_BASKET_QUEUE}>>')
            self._window_child_extend_downloading.protocol("WM_DELETE_WINDOW", _prepare_to_close)

        def _preparing_to_full_download():
            # Формируем датафрейм для дальнейшей отправки его в загрузчик

            action_type = config.Actions.actions_dict[_combobox_action_type.current()]
            data_frame = {action_type: {}, config.Actions.check_actions['id']: self._check_add_ids.get(),
                          config.Actions.check_actions['rw']: self._check_rewritable.get(),
                          config.Actions.check_actions['hist']: self._check_state_history.get()}

            for _playlist in self._wrapper.playlists:
                if _playlist.kind not in self._wrapper.marked_up_data:
                    # Если данных о текущем плейлисте нет, то скачиваем их
                    self._wrapper.data_markup(_playlist.kind)

            # Формируем датафрейм
            for playlist_kind, playlist_data in self._wrapper.marked_up_data.items():
                data_frame[action_type][playlist_kind] = playlist_data

            # Отчищаем всё из корзины для текущего экшена
            if action_type in basket:
                del basket[action_type]

            _load_playlist_data_to_tree_view2()

            self._wrapper.basket_queue.put(data_frame)
            self._window_main.event_generate(f'<<{self.Events.CHECK_BASKET_QUEUE}>>')
            self._window_child_extend_downloading.protocol("WM_DELETE_WINDOW", _prepare_to_close)

        _thread_event = tk.BooleanVar(value=False)
        _thread_event.trace_add('write', _load_playlist_data_to_tree_view1)

        _thread = threading.Thread(target=self._wrapper.data_markup,
                                   args=[self._wrapper.playlists[0].kind, _thread_event], daemon=True)
        _thread.start()

        _frame_window_child = ttk.Frame(self._window_child_extend_downloading)
        _frame_window_child.pack(expand=1, fill=tk.BOTH)

        # Создаем фрейм для комбобоксов
        _labelframe_comboboxes = ttk.LabelFrame(_frame_window_child, text='Выберете плейлист и действие с ним')
        _labelframe_comboboxes.pack(padx=5, pady=5)

        _frame_combo_action = ttk.Frame(_labelframe_comboboxes)
        _frame_combo_action.grid(column=0, row=0, padx=5, pady=5)

        # Комбобокс дейтвий
        _combobox_action_type = widgets.JustifiedCombobox(_frame_combo_action, width=40, validate='focusout',
                                                          state="readonly", justify=tk.CENTER,
                                                          validatecommand=(
                                                              self._window_child_extend_downloading.register(
                                                                  _combo_action_was_updated), '%P'))
        _combobox_action_type.bind('<<ComboboxSelected>>', _combo_action_was_updated)
        _combobox_action_type.pack()

        # Заполняем его
        for action in config.Actions.actions_list_text:
            _combobox_action_type['values'] = (*_combobox_action_type['values'], f'{action}')
        _combobox_action_type.current(0)

        _frame_combo_playlist = ttk.Frame(_labelframe_comboboxes)
        _frame_combo_playlist.grid(column=1, row=0, padx=5, pady=5)

        # Комбобокс плейлистов
        _combobox_playlists = widgets.JustifiedCombobox(_frame_combo_playlist, width=40, validate='focusout',
                                                        state="readonly", justify=tk.CENTER,
                                                        validatecommand=(
                                                            self._window_child_extend_downloading.register(
                                                                _combo_playlists_was_updated), '%P'))
        _combobox_playlists.bind('<<ComboboxSelected>>', _combo_playlists_was_updated)
        _combobox_playlists.pack()

        # Заполняем его
        for playlist in self._wrapper.playlists:
            _combobox_playlists['values'] = (*_combobox_playlists['values'], f'{playlist.title}')
        _combobox_playlists.current(0)

        # Фрейм для плейлиста
        _frame_playlist = ttk.Frame(_frame_window_child)
        _frame_playlist.pack(expand=1, fill=tk.BOTH, padx=5, pady=5)

        # Фрейм для поиска
        _frame_search = ttk.Frame(_frame_playlist)
        _frame_search.pack(padx=10, pady=10)

        _label_search = ttk.Label(_frame_search, text='Поиск:')
        _label_search.grid(column=0, row=0, sticky=tk.E, padx=10, pady=10)

        _entry_string_variable = tk.StringVar()
        _entry_string_variable.trace_add("write",
                                         lambda name, index, mode, sv=_entry_string_variable: _entry_was_changed(sv))
        _entry_search_track = ttk.Entry(_frame_search, width=40, textvariable=_entry_string_variable)
        _entry_search_track.grid(column=1, row=0, columnspan=2, sticky=tk.EW, padx=10, pady=10)

        _notebook = ttk.Notebook(_frame_playlist)
        _notebook.pack(expand=1, fill=tk.BOTH, padx=5, pady=5)

        _frame_notebook_tab1 = ttk.Frame(_notebook)
        _notebook.add(_frame_notebook_tab1, text='Список всех композиций')

        def _tree_view_sort(_col, tree_view_num, reverse):
            if tree_view_num == 1:
                _tree_view_tab1.tv_simple_sorting(_col, reverse)
                _tree_view_tab1.tv_heading(_col, command=lambda _col=_col: _tree_view_sort(_col, 1, not reverse))
            else:
                if _col:
                    _tree_view_tab2.tv_nested_sorting_children(_col, reverse)
                else:
                    _tree_view_tab2.tv_simple_sorting(_col, reverse)
                _tree_view_tab2.tv_heading(f'#{_col}', command=lambda _col=_col: _tree_view_sort(_col, 2, not reverse))

        _tree_view_tab1 = widgets.ScrollingTreeView(_frame_notebook_tab1, selectmode="extended", columns=(1, 2, 3),
                                                    height=12)
        _tree_view_tab1.pack(expand=1, fill=tk.BOTH, padx=5, pady=5)

        # TreeView columns main
        _tree_view_tab1.tv_column("#0", width=0, stretch=tk.NO)
        for col in range(1, 4):
            _tree_view_tab1.tv_column(col, anchor="w", width=120)

        # TreeView headings
        _tree_view_columns = ['Плейлист', 'Композиция', 'Исполнитель', 'Альбом']
        _reverse = [False, True, False, False]

        _tree_view_tab1.tv_heading("#0", text="", anchor="center")
        for col in range(1, 4):
            _tree_view_tab1.tv_heading(col, text=_tree_view_columns[col], anchor="center",
                                       command=lambda _col=col, rev=_reverse[col]: _tree_view_sort(_col, 1, rev))

        # Фрейм для кнопок добавления
        _frame_button_add = ttk.Frame(_frame_notebook_tab1)
        _frame_button_add.pack(padx=5, pady=5)

        _button_add_all = ttk.Button(_frame_button_add, text='Добавить плейлист в корзину', width=40,
                                     command=_add_playlist_to_basket)
        _button_add_all.grid(row=0, column=0, padx=5, pady=5)

        _button_add_selected = ttk.Button(_frame_button_add, text='Добавить выбранное в корзину', width=40,
                                          command=_add_partial_playlist_to_basket)
        _button_add_selected.grid(row=0, column=1, padx=5, pady=5)

        _frame_notebook_tab2 = ttk.Frame(_notebook)
        _notebook.add(_frame_notebook_tab2, text='Корзина')

        _tree_view_tab2 = widgets.ScrollingTreeView(_frame_notebook_tab2, selectmode="extended", columns=(1, 2, 3),
                                                    height=12)
        _tree_view_tab2.pack(expand=1, fill=tk.BOTH, padx=5, pady=5)

        # TreeView columns selected
        for col in range(4):
            _tree_view_tab2.tv_column(col, anchor="w", width=150)
        _tree_view_tab2.tv_column('#0', stretch=tk.NO)

        # TreeView headings
        for col in range(4):
            _tree_view_tab2.tv_heading(f'#{col}', text=_tree_view_columns[col], anchor="center",
                                       command=lambda _col=col, rev=_reverse[col]: _tree_view_sort(_col, 2, rev))

        # Фрейм для кнопок удаления
        _frame_button_delete = ttk.Frame(_frame_notebook_tab2)
        _frame_button_delete.pack(padx=5, pady=5)

        _button_clear_basket = ttk.Button(_frame_button_delete, text='Удалить всё из корзины', width=40,
                                          command=_clear_basket)
        _button_clear_basket.grid(row=0, column=0, padx=5, pady=5)

        _button_delete_all = ttk.Button(_frame_button_delete, text='Удалить плейлист из списока', width=40,
                                        command=_delete_playlist_from_basket)
        _button_delete_all.grid(row=0, column=1, padx=5, pady=5)

        _button_delete_selected = ttk.Button(_frame_button_delete, text='Удалить выбранное из списока', width=40,
                                             command=_delete_partial_playlist_from_basket)
        _button_delete_selected.grid(row=0, column=2, padx=5, pady=5)

        # Фрейм чекбоксов
        _frame_checkboxes = ttk.Frame(_frame_playlist)
        _frame_checkboxes.pack(padx=5, pady=5)

        self._check_rewritable = tk.BooleanVar(value=self._is_rewritable)
        _checkbox_rewritable = ttk.Checkbutton(_frame_checkboxes,
                                               text="Перезаписывать существующие композиции",
                                               width=45, var=self._check_rewritable)
        _checkbox_rewritable.grid(row=0, column=1, padx=15, pady=5)

        self._check_add_ids = tk.BooleanVar(value=False)
        _checkbox_add_ids = ttk.Checkbutton(_frame_checkboxes, text="Добавлять id трека к названию",
                                            width=30, var=self._check_add_ids)
        _checkbox_add_ids.grid(row=0, column=0, padx=15, pady=5)

        _checkbox_history_db = ttk.Checkbutton(_frame_checkboxes, text="Скачивать только новые треки",
                                               width=30, var=self._check_state_history)
        _checkbox_history_db.grid(row=0, column=2, padx=15, pady=5)

        # Фейм кнопок для загрузки
        _frame_download = ttk.Frame(_frame_playlist)
        _frame_download.pack(padx=5, pady=5)

        _current_action_text = config.Actions.actions_list_text_short[_combobox_action_type.current()]
        _button_download_all_postfix_text = " все плейлисты"
        _button_download_selected_postfix_text = " всё из корзины"

        _button_download_all_allow_states = len(config.Actions.actions_list_text_short) * [True]
        _button_download_selected_allow_states = len(config.Actions.actions_list_text_short) * [True]

        _button_download_all = ttk.Button(_frame_download,
                                          text=f'{_current_action_text}{_button_download_all_postfix_text}',
                                          width=40, command=lambda: _prepare_to_download(False))
        _button_download_all.grid(row=0, column=0, padx=5, pady=5)

        _button_download_selected = ttk.Button(_frame_download,
                                               text=f'{_current_action_text}{_button_download_selected_postfix_text}',
                                               width=40, command=lambda: _prepare_to_download())
        _button_download_selected.grid(row=0, column=1, padx=5, pady=5)

    def _create_new_download_instance(self, close_function, pause_function, number_of_playlists, action_type):

        def _close_function():
            logger.debug(f'Удаляю вкладку из окна загрузки. '
                         f'Имя: [{config.Actions.actions_dict_text[action_type]}].')
            self._notebook_download.forget(self._notebook_download.select())
            thread = threading.Thread(target=close_function, daemon=True)
            thread.start()
            frame.destroy()

            # Добавить переход на первую вкладку и закритие окна
            if not self._notebook_download.index('end'):
                self._window_download.withdraw()
            else:
                self._notebook_download.select(0)

        def _pause_function():
            nonlocal is_paused, pause_text
            is_paused = not is_paused
            pause_text = pause_list[0] if not is_paused else pause_list[1]

            button_pause.config(text=pause_text)
            pause_function()

        self._window_download.deiconify()

        logger.debug(f'Добавляю новую вкладку в окно загрузки. '
                     f'Имя: [{config.Actions.actions_dict_text[action_type]}].')

        frame = ttk.Frame(self._notebook_download)
        frame.pack(padx=5, pady=5, expand=1, fill=tk.BOTH)

        frame_buttons = ttk.Frame(frame)
        frame_buttons.pack(padx=5, pady=5)

        is_paused = False
        pause_list = ['Остановить', 'Возобновить']
        pause_text = pause_list[0] if not is_paused else pause_list[1]

        button_pause = ttk.Button(frame_buttons, text=pause_text, command=_pause_function)
        button_pause.pack(padx=5, side=tk.LEFT)
        button_close = ttk.Button(frame_buttons, text='Завершить', command=_close_function)
        button_close.pack(padx=5, side=tk.LEFT)

        scrolling_frame = widgets.ScrollingFrame(frame)
        scrolling_frame.pack(expand=True, fill=tk.BOTH)

        widgets_variables = []
        for i in range(number_of_playlists):
            download_widget = scrolling_frame.add_widget(action_type=action_type)
            scrolling_frame.w_pack(download_widget, pady=5)
            widgets_variables.append(download_widget.get_variables())

        self._notebook_download.add(frame, text=f'{config.Actions.actions_dict_text[action_type]}')

        return widgets_variables

    class Events(StrEnum):
        PLAYLISTS_INFO_LOADED = auto()
        COVERS_LOADED = auto()
        CHECK_BASKET_QUEUE = auto()
        MAIN_WINDOW_CLOSE = auto()

    class DownloaderWrapper:
        def __init__(self, token, _history_database_path, _download_folder_path, _playlists_covers_folder_name,
                     _is_rewritable, _event, _create_download_instance):
            self.token = token
            self._history_database_path = _history_database_path
            self._download_folder_path = _download_folder_path
            self._playlists_covers_folder_name = _playlists_covers_folder_name
            self._is_rewritable = _is_rewritable
            self._event = _event
            self._create_download_instance = _create_download_instance

            self._client = None
            self._liked_tracks = []
            self._actioned_playlists = {}

            self.wrapper_state_is_ok = False
            self.playlists = []
            self.playlists_titles = {}

            self.marked_up_data = {}
            self.playlists_are_marking_up = []
            self.basket_queue = Queue()

            self.main_window_state = True
            self.number_of_workers = config.NUMBER_OF_WORKERS

            self._download_threads = []
            self._download_workers_threads = []

        def init(self):
            """
            Загружаем название плейлистов, обложки и тд. + обновляем состояние всех виджетов

            :return:
            """

            try:
                # Проверяем введённый токен на валидность
                try:
                    Client.notice_displayed = True
                    self._client = Client(token=self.token)
                    self._client.init()
                    logger.debug('Введённый токен валиден, авторизация прошла успешно!')
                except UnauthorizedError:
                    logger.error('Введен невалидный токен!')
                    messagebox.showerror('Ошибка', 'Введенный токен невалиден!')
                    return

                self.wrapper_state_is_ok = True

                unsorted_playlists = self._client.users_playlists_list()
                playlists = sorted(unsorted_playlists, key=lambda dct: dct.title)
                self._liked_tracks = self._client.users_likes_tracks()

                favorite_playlist = copy.deepcopy(playlists[-1])
                favorite_playlist.title = 'Любимое'
                favorite_playlist.kind = 3
                favorite_playlist.cover = None
                favorite_playlist.track_count = len(self._liked_tracks)

                playlists.insert(0, favorite_playlist)
                self.playlists = playlists

                # Формируем словарь playlist_kind: playlist_title
                for playlist in self.playlists:
                    self.playlists_titles[playlist.kind] = playlist.title

                self._event.event_generate(f'<<{YandexMusicDownloader.Events.PLAYLISTS_INFO_LOADED}>>')

                # Скачиваем все обложки всех плейлистов
                thread = threading.Thread(target=self._download_all_playlists_covers, daemon=True)
                thread.start()
            except NetworkError:
                messagebox.showerror('Ошибка', 'Не удалось подключиться к Yandex!\n\nПопробуйте позже.')

            self._event.bind(f'<<{YandexMusicDownloader.Events.CHECK_BASKET_QUEUE}>>', self._check_queue)
            self._event.bind(f'<<{YandexMusicDownloader.Events.MAIN_WINDOW_CLOSE}>>', self.break_download)

        def _download_all_playlists_covers(self):
            """
            Скачиваем все обложки всех плейлистов

            :return:
            """
            for playlist in self.playlists:
                if playlist.cover:
                    if playlist.cover.items_uri is not None:
                        playlist_title = utils.strip_bad_symbols(playlist.title)
                        if not os.path.exists(f'{self._playlists_covers_folder_name}/{playlist_title}.jpg'):
                            try:
                                playlist.cover.download(
                                    filename=f'{self._playlists_covers_folder_name}/{playlist_title}.jpg',
                                    size='100x100')
                                logger.debug(f'Обложка для плейлиста [{playlist_title}] была загружена в '
                                             f'[{self._playlists_covers_folder_name}/{playlist_title}.jpg].')
                            except NetworkError:
                                messagebox.showerror('Ошибка', 'Не удалось подключиться к Yandex!\nПопробуйте позже.')
                                return
                        else:
                            logger.debug(f'Обложка для плейлиста [{playlist_title}] уже существует в '
                                         f'[{self._playlists_covers_folder_name}/{playlist_title}.jpg].')

            self._event.event_generate(f'<<{YandexMusicDownloader.Events.COVERS_LOADED}>>')

        def get_playlists_data(self, kind):
            """
            Возвращает список данных о каждом плейлите, указаном в kind

            :param kind: index плейлиста
            :return:
            """
            return self._client.users_playlists(kind=kind)

        def data_markup(self, kind, event=None):
            """
            Создаем JSON формат данных для дальнейшей работы

            :param kind: Номер плейлиста
            :param event: Событие завершения
            :return:
            """
            if kind not in self.marked_up_data:
                self.playlists_are_marking_up.append(kind)

                # Загружаем данные о плейлистах
                playlist_data = self.get_playlists_data(kind)

                # Проверка, если по какой-то причине треки не пришли
                if playlist_data.tracks:
                    if playlist_data.tracks[0].track is None:
                        playlist_data.tracks = playlist_data.fetch_tracks()

                # Размечаем данные для каждого плейлиста
                self.marked_up_data.update({playlist_data.kind: []})
                for _track in playlist_data.tracks:
                    self.marked_up_data[playlist_data.kind].append({
                        'track': _track.track,
                        'artists': ', '.join(artists.name for artists in _track.track.artists),
                        'albums': ', '.join(album.title for album in _track.track.albums),
                        'title': _track.track.title + (
                            "" if _track.track.version is None else f' ({_track.track.version})'),
                        'id': _track.track.id
                    })

                    self.marked_up_data[playlist_data.kind].sort(key=itemgetter('title'))

                self.playlists_are_marking_up.remove(kind)

            if event is not None:
                event.set(not event.get())

        def _check_queue(self, *args):
            """
            Создаем отдельный поток для обработки текущего датафрейма в очереди

            :return:
            """
            thread = threading.Thread(target=self._read_queue, daemon=True)
            thread.start()

        def _read_queue(self):
            """
            Считываем датафрейм из очереди, разбиваем на части и отправляем в загрузчик

            :return:
            """
            logger.debug(f'Начинаю распаршивать датафрейм.')

            data_frame = self.basket_queue.get()
            playlists_queue = Queue()
            action_type = None

            for key, playlists in data_frame.items():
                if key in config.Actions.actions_list:
                    action_type = key
                    logger.debug(f'Текущий датафрейм содержит в себе {len(playlists)} плейлиста(-ов). Действие:'
                                 f' [{config.Actions.actions_dict_text[action_type]}].')
                    for playlist_kind, playlist_data in playlists.items():
                        playlists_queue.put((self.playlists_titles[playlist_kind], playlist_data))

            if not playlists_queue.empty():
                logger.debug(f'Отправляю плейлисты на загрузку.')
                thread = threading.Thread(target=self._download_playlists,
                                          args=[playlists_queue, action_type, {
                                              config.Actions.check_actions['id']:
                                                  data_frame[config.Actions.check_actions['id']],
                                              config.Actions.check_actions['rw']:
                                                  data_frame[config.Actions.check_actions['rw']],
                                              config.Actions.check_actions['hist']:
                                                  data_frame[config.Actions.check_actions['hist']]
                                          }],
                                          daemon=True)
                self._download_threads.append(thread)
                thread.start()

        def break_download(self, *args):
            self.main_window_state = False

            for worker in self._download_workers_threads:
                logger.debug(f'Устанавливая флаг завершения для потока [{worker.ident}].')
                worker.close()

            # Ожидаем их завершения
            for worker in self._download_workers_threads:
                logger.debug(f'Ожидание завершения потока (worker) [{worker.ident}].')
                worker.join()
                logger.debug(f'Поток (worker) [{worker.ident}] был завершён.')

            for thread in self._download_threads:
                logger.debug(f'Ожидание завершения потока [{thread.ident}].')
                thread.join()
                logger.debug(f'Поток [{thread.ident}] был завершён.')

        def _download_playlists(self, playlists_queue, action_type, special_modes):
            """
                Загружаем сформированные плейлисты

                :param playlists_queue: Очередь (название плейлиста, данные)
                :param action_type: Тип экшена загрузка/обновление/...
                :param special_modes: {id, rewritable, history}
                :return:
                """

            is_finishing_downloading = False

            logger.debug(f'Начинаю распаршивать датафрейм.')

            def _pause_download():
                for _worker in workers:
                    logger.debug(f'Устанавливая/Снимаю флаг паузы для потока [{_worker.ident}].')
                    _worker.pause()

            def _break_download():
                for _worker in workers:
                    logger.debug(f'Устанавливая флаг завершения для потока [{_worker.ident}].')
                    _worker.close()

                # Ожидаем их завершения
                for _worker in workers:
                    logger.debug(f'Ожидание завершения потока (worker) [{_worker.ident}].')
                    _worker.join()
                    logger.debug(f'Поток (worker) [{_worker.ident}] был завершён.')

                nonlocal is_finishing_downloading
                is_finishing_downloading = True

            # Добавляем в окно загрузки
            widgets_variables = self._create_download_instance(
                close_function=_break_download,
                pause_function=_pause_download,
                number_of_playlists=playlists_queue.qsize(),
                action_type=action_type
            )

            mutex = threading.Lock()

            # Создаем воркеров
            workers = []
            logger.debug(f'Создаю {self.number_of_workers} воркера(-ов) для работы.')
            for i in range(self.number_of_workers):
                worker = self.DownloaderHelper(
                    mutex=mutex,
                    tracks_queue=None,
                    action_type=action_type,
                    special_modes=special_modes
                )
                worker.setDaemon(True)
                worker.set_history_database(self._history_database_path)
                worker.set_favorite_tracks(self._liked_tracks)

                worker.start()
                workers.append(worker)
                self._download_workers_threads.append(worker)

            playlist_counter = 0
            while not playlists_queue.empty():
                if self.main_window_state is False:
                    logger.debug(f'Главное окно получило команду на завершение. Выхожу.')
                    return
                elif is_finishing_downloading is True:
                    logger.debug(f'Поток текущей загрузки получил команду на завершение. Выхожу.')
                    return

                playlist_title, playlist_data = playlists_queue.get()

                # Меняем значения у виджетов
                widgets_variables[playlist_counter][1].set(len(playlist_data))
                widgets_variables[playlist_counter][2].set(playlist_title)

                time.sleep(0.1)

                tracks_queue = Queue()

                logger.debug(f'Начинаю работу с плейлистом [{playlist_title}]. '
                             f'Действие: [{config.Actions.actions_dict_text[action_type]}].')

                # Создаем папку плейлиста
                download_folder_path = f'{self._download_folder_path}/{utils.strip_bad_symbols(playlist_title)}'
                if os.path.exists(download_folder_path):
                    logger.debug(f'Директория [{download_folder_path}] уже существует.')
                else:
                    logger.debug(f'Директория [{download_folder_path}] была создана.')
                    os.makedirs(f'{download_folder_path}', exist_ok=True)

                if os.path.exists(f'{download_folder_path}/covers'):
                    logger.debug(f'Директория [{download_folder_path}/covers] уже существует.')
                else:
                    logger.debug(f'Директория [{download_folder_path}/covers] была создана.')
                    os.makedirs(f'{download_folder_path}/covers', exist_ok=True)

                if os.path.exists(f'{download_folder_path}/info'):
                    logger.debug(f'Директория [{download_folder_path}/info] уже существует.')
                else:
                    logger.debug(f'Директория [{download_folder_path}/info] была создана.')
                    os.makedirs(f'{download_folder_path}/info', exist_ok=True)

                with open(f'{download_folder_path}/info/errors.txt', 'w', encoding='utf-8') as file:
                    pass
                with open(f'{download_folder_path}/info/downloaded.txt', 'w', encoding='utf-8') as file:
                    pass

                # Меняем значения у воркеров
                for worker in workers:
                    worker.set_tracks_queue(tracks_queue)
                    worker.set_playlist_title(playlist_title)
                    worker.set_download_folder(download_folder_path)
                    worker.set_download_progress_var(widgets_variables[playlist_counter][0])

                # Начинаем заполнять очередь треков
                for playlist_track in playlist_data:
                    tracks_queue.put(playlist_track)

                while not tracks_queue.empty():
                    if self.main_window_state is False:
                        logger.debug(f'Главное окно получило команду на завершение. Выхожу.')
                        return
                    elif is_finishing_downloading is True:
                        logger.debug(f'Поток текущей загрузки получил команду на завершение. Выхожу.')
                        return
                    time.sleep(0.1)

                # Закончили работать с текущим плейлистом
                were_downloaded_tracks = 0
                were_not_downloaded_tracks = 0
                for worker in workers:
                    while worker.get_state() is True:
                        time.sleep(0.1)

                    were_downloaded_tracks += worker.downloaded_tracks
                    were_not_downloaded_tracks += worker.not_downloaded_tracks
                    worker.downloaded_tracks = 0
                    worker.not_downloaded_tracks = 0
                widgets_variables[playlist_counter][-2].set(were_downloaded_tracks)
                widgets_variables[playlist_counter][-1].set(were_not_downloaded_tracks)

                playlist_counter += 1
                time.sleep(0.1)

            logger.debug(f'Действие: [{config.Actions.actions_dict_text[action_type]}].'
                         f' Работа завершена - выхожу.')
            _break_download()

        class DownloaderHelper(threading.Thread):
            def __init__(self, mutex, tracks_queue, action_type, special_modes):
                threading.Thread.__init__(self)

                self.mutex = mutex

                self.tracks_queue = tracks_queue
                self.action_type = action_type
                self.special_modes = special_modes

                self.playlist_title = None
                self.download_folder_path = None
                self.history_database_path = None

                self.favorite_tracks = None

                self.download_progress = None
                self.downloaded_tracks = 0
                self.not_downloaded_tracks = 0

                self._close_worker = False
                self._pause_worker = False
                self._state_working = False

            def run(self):
                while not self._close_worker:
                    if self._pause_worker is False:
                        if self.tracks_queue is not None:
                            self.mutex.acquire()
                            if not self.tracks_queue.empty():
                                try:
                                    self._state_working = True
                                    logger.debug(f'Получаю данные из очереди.')
                                    data = self.tracks_queue.get()
                                    logger.debug(f'Получил данные из очереди.')
                                    self.mutex.release()

                                    if self._do_work(data):
                                        self._increase_progress()
                                except NetworkError:
                                    logger.error('Не удалось связаться с сервисом Яндекс Музыка!')
                                    self.not_downloaded_tracks += 1
                                    self._increase_progress()
                                    break
                            else:
                                self._state_working = False
                                logger.debug(f'Очередь пуста.')
                                self.mutex.release()
                    time.sleep(0.01)

            def _increase_progress(self):
                self.mutex.acquire()
                self.download_progress.set(self.download_progress.get() + 1)
                self.mutex.release()

            def _do_work(self, track_data):
                if self.action_type == 'd':
                    return self._download_track(track_data)
                elif self.action_type == 'u':
                    return self._update_track_metadata(track_data)
                elif self.action_type == 'adb':
                    return self._add_track_to_database(track_data)
                elif self.action_type == 'uf':
                    return self._update_liked_track_in_database(track_data)

            def set_history_database(self, history_database_path):
                self.history_database_path = history_database_path

            def set_playlist_title(self, playlist_title):
                self.playlist_title = utils.strip_bad_symbols(playlist_title).replace(' ', '_')

            def set_download_folder(self, download_folder_path):
                self.download_folder_path = download_folder_path

            def set_tracks_queue(self, tracks_queue):
                self.tracks_queue = tracks_queue

            def set_download_progress_var(self, download_progress_var):
                self.download_progress = download_progress_var

            def set_favorite_tracks(self, favorite_tracks):
                self.favorite_tracks = favorite_tracks

            def close(self):
                self._close_worker = True

            def pause(self):
                self._pause_worker = not self._pause_worker

            def get_state(self):
                """
                Возвращает статус воркера

                :return: True - работает, False - нет
                """
                return self._state_working

            def _download_track(self, track_data):
                """
                   Скачивает полученный трек, параллельно добавляя о нём всю доступную информацию в базу данных.
                   :param track_data: текущий трек
                   :return: True - если все нормально скачалось
                """
                if self._close_worker is True:
                    return False

                track_name = self._get_track_name(track_data)

                # Если загружать только новые
                if self.special_modes[config.Actions.check_actions['hist']]:
                    if self._is_track_in_database(track_data):
                        logger.debug(f'Трек [{track_name}] уже существует в базе '
                                     f'[{self.history_database_path}]. Так как включён мод ONLY_NEW, выхожу.')
                        return True
                    else:
                        logger.debug(f'Трека [{track_name}] нет в базе '
                                     f'[{self.history_database_path}]. Подготавливаюсь к его загрузки.')

                try:
                    if not track_data['track'].available:
                        logger.error(f'Трек [{track_name}] недоступен.')
                        self.mutex.acquire()
                        with open(f"{self.download_folder_path}/info/errors.txt", 'a', encoding='utf-8') as file:
                            file.write(f"{track_name} ~ Трек недоступен\n")
                        self.mutex.release()
                        self.not_downloaded_tracks += 1
                        return True

                    was_track_downloaded = False
                    track_exists = False
                    for info in sorted(track_data['track'].get_download_info(), key=lambda x: x['bitrate_in_kbps'], reverse=True):
                        codec = info.codec
                        bitrate = info.bitrate_in_kbps
                        full_track_name = os.path.abspath(f'{self.download_folder_path}/{track_name}.{codec}')

                        # Если трек существует и мы не перезаписываем, то выходим, но скачала проеверяем, есть ли он в базе
                        if os.path.exists(f'{full_track_name}') and not self.special_modes[config.Actions.check_actions['rw']]:
                            logger.debug(f'Трек [{track_name}] уже существует на диске '
                                         f'[{self.download_folder_path}]. Проверяю в базе.')

                            if self._is_track_in_database(track_data):
                                logger.debug(f'Трек [{track_name}] уже существует в базе '
                                             f'[{self.history_database_path}]. Так как отключена перезапись, выхожу.')
                            else:
                                logger.debug(f'Трек [{track_name}] отсутствует в базе '
                                             f'[{self.history_database_path}]. Так как отключена перезапись, просто '
                                             f'добавляю его в базу и выхожу.')
                                self.__add_track_to_database(track_data=track_data,
                                                             codec=codec,
                                                             bit_rate=bitrate,
                                                             is_favorite=self._is_favorite_track(track_data['id'])
                                                             )
                                logger.debug(
                                    f'Трек [{track_name}] был добавлен в базу данных [{self.history_database_path}].')
                            track_exists = True
                            break

                        try:
                            if self._close_worker is True:
                                return False

                            logger.debug(f'Начинаю загрузку трека [{track_name}].')
                            track_data['track'].download(filename=full_track_name, codec=codec, bitrate_in_kbps=bitrate)
                            logger.debug(f'Трек [{track_name}] был скачан.')

                            self.mutex.acquire()
                            with open(f"{self.download_folder_path}/info/downloaded.txt", 'a', encoding='utf-8') as file:
                                file.write(f'{track_name}\n')
                            self.mutex.release()

                            cover_filename = os.path.abspath(f'{self.download_folder_path}/covers/{track_name}.jpg')
                            if not os.path.exists(cover_filename):
                                logger.debug(f'Обложка для трека [{track_name}] не найдена, начинаю загрузку.')
                                track_data['track'].download_cover(cover_filename, size="300x300")
                                logger.debug(f'Обложка для трека [{track_name}] была скачана в [{cover_filename}].')

                            try:
                                album_info = track_data['track'].albums[0]
                                genre = album_info.genre if album_info is not None else ""
                                track_number = album_info.track_position.index if album_info is not None else 0
                                disk_number = album_info.track_position.volume if album_info is not None else 0
                                year = album_info.year if album_info is not None else 0
                                album_artists = album_info.artists if album_info is not None else ""

                                lyrics = track_data['track'].get_supplement().lyrics
                                self._write_track_metadata(full_track_name=full_track_name,
                                                           track_title=track_data['title'],
                                                           artists=track_data['artists'],
                                                           albums=track_data['albums'],
                                                           genre=genre,
                                                           album_artists=album_artists,
                                                           year=year,
                                                           cover_filename=cover_filename,
                                                           track_position=track_number,
                                                           disk_number=disk_number,
                                                           lyrics=lyrics)
                                logger.debug(f'Метаданные трека [{track_name}] были обновлены.')
                            except AttributeError:
                                logger.error(f'Не удалось обновить метаданные для файла [{full_track_name}].')
                            except TypeError:
                                logger.error(f'Не удалось обновить метаданные для файла [{full_track_name}].')

                            if not self._is_track_in_database(track_data):
                                logger.debug(f'Трек [{track_name}] отсутствует в базе данных по пути '
                                             f'[{self.history_database_path}]. Добавляю в базу.')
                                self.__add_track_to_database(track_data=track_data,
                                                             codec=codec,
                                                             bit_rate=bitrate,
                                                             is_favorite=self._is_favorite_track(track_data['id'])
                                                             )
                                logger.debug(
                                    f'Трек [{track_name}] был добавлен в базу данных [{self.history_database_path}].')
                            else:
                                logger.debug(f'Трек [{track_name}] уже присутствует в базе данных по пути '
                                             f'[{self.history_database_path}].')

                            self.downloaded_tracks += 1
                            was_track_downloaded = True
                            break
                        except (YandexMusicError, TimeoutError):
                            logger.debug(
                                f'Не удалось скачать трек [{track_name}] с кодеком [{codec}] и битрейтом [{bitrate}].')
                            continue

                    if was_track_downloaded is False:
                        if track_exists is False:
                            logger.error(f'Не удалось скачать трек [{track_name}].')
                            self.mutex.acquire()
                            with open(f"{self.download_folder_path}/info/errors.txt", 'a', encoding='utf-8') as file:
                                file.write(f"{track_name} ~ Не удалось скачать трек\n")
                            self.mutex.release()
                            self.not_downloaded_tracks += 1

                except IOError:
                    logger.error(f'Ошибка при попытке записи в файла.')
                    self.not_downloaded_tracks += 1
                return True

            def _update_track_metadata(self, track_data):
                """
                    Обновляет метаданные трека
                    :param track_data: текущий трек
                    :return:
                """
                track_name = self._get_track_name(track_data)

                if self._close_worker is True:
                    return False

                if not track_data['track'].available:
                    logger.error(f'Трек [{track_name}] недоступен.')
                    self.mutex.acquire()
                    with open(f"{self.download_folder_path}/info/errors.txt", 'a', encoding='utf-8') as file:
                        file.write(f"{track_name} ~ Трек недоступен\n")
                    self.mutex.release()
                    self.not_downloaded_tracks += 1
                    return True

                def _error_func():
                    self.not_downloaded_tracks += 1
                    self.mutex.acquire()
                    with open(f"{self.download_folder_path}/info/errors.txt", 'a', encoding='utf-8') as file1:
                        file1.write(f"Не удалось обновить метаданные для файла [{full_track_name}].\n")
                    self.mutex.release()
                    logger.error(f'Не удалось обновить метаданные для файла [{full_track_name}].')

                # Пытаемся найти данных трек с разными доступными кодеками
                for info in sorted(track_data['track'].get_download_info(), key=lambda x: x['bitrate_in_kbps'], reverse=True):
                    codec = info.codec
                    full_track_name = os.path.abspath(f'{self.download_folder_path}/{track_name}.{codec}')

                    # Если трек существует, обновляем метаданные
                    if os.path.exists(full_track_name):
                        logger.debug(f'Трек [{track_name}] присутствует на диске '
                                     f'[{self.download_folder_path}]. Пытаюсь обновить метаданные.')

                        cover_filename = os.path.abspath(f'{self.download_folder_path}/covers/{track_name}.jpg')
                        if not os.path.exists(cover_filename):
                            logger.debug(f'Обложка для трека [{track_name}] не найдена, начинаю загрузку.')
                            track_data['track'].download_cover(cover_filename, size="300x300")
                            logger.debug(f'Обложка для трека [{track_name}] была скачана в [{cover_filename}].')
                        try:
                            album_info = track_data['track'].albums[0]
                            genre = album_info.genre if album_info is not None else ""
                            track_number = album_info.track_position.index if album_info is not None else 0
                            disk_number = album_info.track_position.volume if album_info is not None else 0
                            year = album_info.year if album_info is not None else 0
                            album_artists = album_info.artists if album_info is not None else ""

                            lyrics = track_data['track'].get_supplement().lyrics
                            self._write_track_metadata(full_track_name=full_track_name,
                                                       track_title=track_data['title'],
                                                       artists=track_data['artists'],
                                                       albums=track_data['albums'],
                                                       genre=genre,
                                                       album_artists=album_artists,
                                                       year=year,
                                                       cover_filename=cover_filename,
                                                       track_position=track_number,
                                                       disk_number=disk_number,
                                                       lyrics=lyrics)
                            logger.debug(f'Метаданные трека [{track_name}] были обновлены.')
                            self.downloaded_tracks += 1
                        except AttributeError:
                            _error_func()
                        except TypeError:
                            _error_func()
                        break
                return True

            def _add_track_to_database(self, track_data):
                """
                    Добавляет текущий трек в базу данных, если его там нет
                    :param track_data: текущий трек
                    :return:
                """
                track_name = self._get_track_name(track_data)

                if self._close_worker is True:
                    return False

                if not track_data['track'].available:
                    logger.error(f'Трек [{track_name}] недоступен.')
                    self.mutex.acquire()
                    with open(f"{self.download_folder_path}/info/errors.txt", 'a', encoding='utf-8') as file:
                        file.write(f"{track_name} ~ Трек недоступен\n")
                    self.mutex.release()
                    self.not_downloaded_tracks += 1
                    return True

                if not self._is_track_in_database(track_data):
                    info = sorted(track_data['track'].get_download_info(), key=lambda x: x['bitrate_in_kbps'], reverse=True)[0]
                    codec = info.codec
                    bitrate = info.bitrate_in_kbps

                    logger.debug(f'Трек [{track_name}] отсутствует в базе [{self.history_database_path}].')
                    ret_value = self.__add_track_to_database(
                        track_data=track_data,
                        codec=codec,
                        bit_rate=bitrate,
                        is_favorite=self._is_favorite_track(track_data['id'])
                    )
                    if ret_value:
                        self.downloaded_tracks += 1
                        logger.debug(f'Трек [{track_name}] был добавлен в базу данных [{self.history_database_path}].')
                    else:
                        self.not_downloaded_tracks += 1
                        self.mutex.acquire()
                        with open(f"{self.download_folder_path}/info/errors.txt", 'a', encoding='utf-8') as file:
                            file.write(f"Трек [{track_name}] не удалось добавить в базу данных [{self.history_database_path}].\n")
                        self.mutex.release()
                else:
                    logger.debug(f'Трек [{track_name}] уже существует в базе [{self.history_database_path}].')
                return True

            def _get_track_name(self, track_data, need_strip=True):
                # print(track_data)
                _id_postfix = f" ({track_data['id']})" if self.special_modes[config.Actions.check_actions['id']] else ""
                _track_name = f"{track_data['artists']} - {track_data['title']}{_id_postfix}"

                if need_strip:
                    return utils.strip_bad_symbols(_track_name, soft_mode=True)
                return _track_name

            def _is_track_in_database(self, track_data):
                """
                Ищет трек в базе данных
                :param track_data: трек
                :return: True - если нашел, False - если нет.
                """
                _playlist_name = f'table_{self.playlist_title}'
                _track_name = self._get_track_name(track_data)

                logger.debug(f'Ищу трек [{_track_name}] в базе [{self.history_database_path}].')
                try:
                    with sqlite3.connect(self.history_database_path) as con:
                        cursor = con.cursor()
                        request = f"SELECT * FROM {_playlist_name} WHERE track_id == ? " \
                                  f"OR (track_name == ? " \
                                  f"AND artist_name == ?);"
                        result = cursor.execute(request, [track_data['id'], track_data['title'], track_data['artists']])
                        return True if result.fetchone() else False
                except sqlite3.Error:
                    logger.error(f'Трек [{_track_name}] не удалось проверить в базе данных!')
                    return False

            def __add_track_to_database(self, track_data, codec, bit_rate, is_favorite):
                """
                Добавляет трек в базу данных
                :param track_data: трек
                :param codec: кодек трека
                :param bit_rate: битрейт трека
                :param is_favorite: любимый ли это трек

                :return: True - если все хорошо
                """
                _playlist_name = f'table_{self.playlist_title}'
                _track_name = self._get_track_name(track_data)

                logger.debug(f'Добавляю трек [{_track_name}] в базу [{self.history_database_path}].')

                con = None
                metadata = []
                return_val = True
                try:
                    con = sqlite3.connect(self.history_database_path)
                    cursor = con.cursor()
                    request = f"INSERT INTO {_playlist_name}(" \
                              f"track_id, artist_id, album_id, track_name, artist_name, album_name, genre, track_number, " \
                              f"disk_number, year, release_data, bit_rate, codec, is_favorite, is_explicit, is_popular) " \
                              f"VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?);"

                    album_info = track_data['track'].albums[0]

                    track_id = int(track_data['id'])
                    artist_id = ', '.join(str(i.id) for i in track_data['track'].artists)
                    album_id = ', '.join(str(i.id) for i in track_data['track'].albums)
                    track_name = track_data['title']
                    artist_name = track_data['artists']
                    album_name = track_data['albums']
                    genre = album_info.genre if album_info is not None else ""
                    track_number = album_info.track_position.index if album_info is not None else 0
                    disk_number = album_info.track_position.volume if album_info is not None else 0
                    year = album_info.year if album_info is not None else 0
                    release_data = album_info.release_date if album_info is not None else ""
                    is_explicit = True if track_data['track'].content_warning is not None else False
                    is_popular = True if int(track_data['id']) in album_info.bests else False if album_info is not None else 0

                    metadata = [track_id, artist_id, album_id, track_name, artist_name, album_name,
                                genre, track_number, disk_number, year, release_data, bit_rate, codec,
                                is_favorite, is_explicit, is_popular]

                    cursor.execute(request, metadata)
                    con.commit()

                except AttributeError:
                    return_val = False
                    logger.error(f'Проблемы с тегами.')
                    if con is not None:
                        con.rollback()

                except sqlite3.Error:
                    return_val = False
                    logger.error(f'Не удалось выполнить SQL запрос вставки. Данные: [{metadata}].')
                    if con is not None:
                        con.rollback()
                finally:
                    if con is not None:
                        con.close()
                return return_val

            @staticmethod
            def _write_track_metadata(full_track_name, track_title, artists, albums, genre, album_artists, year,
                                      cover_filename, track_position, disk_number, lyrics):
                """
                Функция для редактирования метаданных трека
                :param full_track_name: путь к треку
                :param track_title: название трека
                :param artists: исполнители
                :param albums: альбомы
                :param genre: жанр
                :param album_artists: исполнители альбома
                :param year: год
                :param cover_filename: путь к обложке
                :param track_position: номер трека в альбоме
                :param disk_number: номер диска (если есть)
                :param lyrics: текст песни (если есть)
                :return:
                """
                file = File(full_track_name)
                with open(cover_filename, 'rb') as cover_file:
                    file.update({
                        # Title
                        'TIT2': mutag.TIT2(encoding=3, text=track_title),
                        # Artist
                        'TPE1': mutag.TPE1(encoding=3, text=artists),
                        # Album
                        'TALB': mutag.TALB(encoding=3, text=albums),
                        # Genre
                        'TCON': mutag.TCON(encoding=3, text=genre),
                        # Album artists
                        'TPE2': mutag.TPE2(encoding=3, text=', '.join(i['name'] for i in album_artists)),
                        # Year
                        'TDRC': mutag.TDRC(encoding=3, text=str(year)),
                        # Picture
                        'APIC': mutag.APIC(encoding=3, text=cover_filename, data=cover_file.read()),
                        # Track number
                        'TRCK': mutag.TRCK(encoding=3, text=str(track_position)),
                        # Disk number
                        'TPOS': mutag.TPOS(encoding=3, text=str(disk_number))
                    })
                if lyrics is not None:
                    # Song lyrics
                    file.tags.add(mutag.USLT(encoding=3, text=lyrics.full_lyrics))
                file.save()

            def _is_favorite_track(self, track_id) -> bool:
                """
                Проверяем, находится ли трек в списке любимых
                :param track_id: идентификатор трека

                :return:
                """
                for track in self.favorite_tracks:
                    if int(track_id) == int(track.id):
                        return True
                return False

            def _update_liked_track_in_database(self, track_data):
                """
                Обновляет список любимых треков в базе данных
                :param track_data: трек

                :return:
                """
                _track_name = self._get_track_name(track_data)
                _playlist_name = f'table_{self.playlist_title}'

                _is_favorite = self._is_favorite_track(track_data['id'])

                con = None
                request = ''
                return_value = True

                try:
                    if not self._is_track_in_database(track_data):
                        logger.debug(f"Трека [{_track_name}] нет в базе данных!")
                        self.not_downloaded_tracks += 1
                        return True

                    con = sqlite3.connect(self.history_database_path)
                    cursor = con.cursor()
                    request = f"UPDATE {_playlist_name} SET is_favorite = ? WHERE track_id == ?;"
                    cursor.execute(request, [_is_favorite, int(track_data['id'])])
                    con.commit()

                    logger.debug(f'Трек [{_track_name}] был добавлен в любимые.')
                    self.downloaded_tracks += 1
                except sqlite3.Error:
                    self.not_downloaded_tracks += 1
                    return_value = False
                    logger.error(f'Не удалось выполнить SQL запрос обновления. Запрос: [{request}].')

                    if con is not None:
                        con.rollback()
                finally:
                    if con is not None:
                        con.close()
                return return_value
