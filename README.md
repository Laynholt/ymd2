# YMD v2.
Новая переосмысленная версия загрузчика Яндекс Музыки. 
Старая версия проекта [https://github.com/Laynholt/ymd]

# Введение
Данное программное приложение предоставляет возможность скачивания композиций из своих плейлистов в Яндекс Музыке. 

Возможно скачать, как полный плейлист целиком, так и оставшуюся часть, которая ещё не была добавлена на устройство. 

Для скачивания музыки необходима авторизация в виде ввода токена, либо логина и пароля.

# Основные зависимости
**Python 3.9 (другие версии не тестировались)**

Данная программа основана на библиотеке yandex-music-api: https://github.com/MarshalX/yandex-music-api

Помимо стандартной темы были использованы темы для tkinter Forest: https://github.com/rdbende/Forest-ttk-theme

# ПО
Программа писалась и тесторовалась на Windows 10 (22H2) и Debian GNU/Linux 11 (bullseye).

# Установка
1) Клонируем репозиторий и переходим в рабочую директорию

```
  git clone https://github.com/Laynholt/ymd2.git
  cd ymd2
```

2) Устанавливаем виртуальное окружение (если хотите, то можете пропутить этот шаг и выполнить только шаг 4)

```
  pip install virtualenv
  virtualenv venv
```

3) Активируем виртуальное окружение

<blockquote>
Для Windows
</blockquote>

```
  .\venv\Scripts\activate
```

<blockquote>
Для Linux
</blockquote>

```
  source venv/bin/activate
```

4) Устанавливаем основные зависимости

```
  pip install -r requirements.txt
```

<blockquote>
Если вы пользователь Linux, то необходимо установить еще модуль tkinter для python3.

В Debian это можно сделать с помощью команды:
</blockquote>
  
```
  sudo apt install python3-tk
```

5) По завершении работы закрываем виртульное окружение

```
  deactivate
```

# Запуск
1) Активация виртуального окружения

<blockquote>
Для Windows
</blockquote>
  
```
  .\venv\Scripts\activate
```

<blockquote>
Для Linux
</blockquote>

```
  source venv/bin/activate
```

2) Работа с проектом и закрытие виртуального окружения

```
  python main.py
  deactivate
```

# Основные отличия от предыдущей версии проекта
**1. Поддержка темной/светлой/стандартной темы.**

**2. Интуитивный интерфейс.**

**3. Общее окно загрузки для всех плейлистов.**

**4. Релизованы все возможности, которые были в TODO у предыдущей версии.**

# Скриншоты
- Окно конфигурации

![image](https://github.com/Laynholt/ymd2/assets/41357381/a8eb3cd3-3ea7-443f-ae7a-1b26c3ae9d59)

![alt text](https://github.com/Laynholt/ymd2/assets/41357381/2dd1cd0e-0dd4-4766-be7f-d882e9e94b55)

- Основное окно программы

![image](https://github.com/Laynholt/ymd2/assets/41357381/20b6cd51-1f0c-4dc3-a74e-5cf2582e7ada)

![image](https://github.com/Laynholt/ymd2/assets/41357381/409a6478-8efb-4336-bc91-767dc261c2aa)


- Окно расширенной загрузки

![image](https://github.com/Laynholt/ymd2/assets/41357381/c83ec330-e5b6-44d0-bb47-982d2fdfc474)

![image](https://github.com/Laynholt/ymd2/assets/41357381/22c86de0-c953-4654-a9f9-f33ac3c85621)

- Окно загрузки

![image](https://github.com/Laynholt/ymd2/assets/41357381/c6d6a1e7-d112-4932-ac63-3760019be6c0)

![image](https://github.com/Laynholt/ymd2/assets/41357381/165d47d0-1da5-439d-ad82-2bc60bae2d77)


## Лицензия

Этот проект лицензирован в соответствии с [Лицензией Apache 2.0](LICENSE).
