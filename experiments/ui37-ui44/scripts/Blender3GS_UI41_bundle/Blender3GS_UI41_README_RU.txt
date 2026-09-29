Blender3GS UI41 MEGA BOOT — экспериментальная сборка по реальной UI40

Цель: ускорить именно ПЕРВУЮ настоящую отрисовку и исключить лишнюю
полную отрисовку ещё не готовых панелей между C-кадром и Python. Не
считать нативный splash полноценным Blender.

Три изменения:
1. Первоначальная C-only отрисовка View3D — Bounding Box, временная;
   сохранённый drawtype восстанавливается в конце прохода. После Python
   Blender отображает сцену с оригинальным shading. Этот быстрый preview
   может выглядеть как рамка вместо затенённого куба.
2. Поздний Python начинает после очередной обработки UIKit-событий через
   33 мс вместо 180 мс. До него не выполняется вторая избыточная
   отрисовка неполного интерфейса. Python выполняется в ОСНОВНОМ потоке;
   примерно 3–4 секунды зависания при импорте остаются реальной проблемой.
3. База предпросмотров ED_preview_init_dbase создаётся после первого кадра;
   промежуточные перерисовки поэтапно загружаемых панелей сокращены.
   Оригинальные модули Python из UI40 IPA не удаляются.

ВНИМАНИЕ: Это эксперимент. Затенение в первом кадре заменено рамкой.
CPU picking, GHOST/жесты и цветовые настройки обычной сцены не меняются.
Работу на устройстве, сокращение секунд и сохранение процесса в фоне
не гарантируем. iOS может выгрузить приложение после Home; UI41 не
изменяет SpringBoard/jetsam/Background Manager и не имитирует фоновой звук.

Перед запуском нужен уже созданный и рабочий файл:
~/Downloads/Blender3GS-python-ui-v40-native-first-frame.ipa
и неизменённый исходный код UI40 под ~/Downloads/blender-ios6-target.
Если source guard STOP — не используйте --resume. Пришлите строку STOP.

СКАЧАТЬ ZIP В DOWNLOADS, СОБРАТЬ И УСТАНОВИТЬ:
cd ~/Downloads && unzip -o Blender3GS_UI41_bundle.zip -d ~/Downloads && bash Blender3GS_UI41_BUILD_INSTALL.command

ПОСЛЕ ОШИБКИ КОМПИЛЯЦИИ (только если появились BACKUP + PATCH):
cd ~/Downloads && bash Blender3GS_UI41_BUILD_INSTALL.command --resume

ПОВТОРНАЯ УСТАНОВКА БЕЗ ПЕРЕСБОРКИ:
cd ~/Downloads && bash Blender3GS_UI41_BUILD_INSTALL.command --install-only

ОТКАТ НА UI40 (сохранённая IPA на Mac):
cd ~/Downloads && bash Blender3GS_UI41_BUILD_INSTALL.command --rollback

ЛОГ ДО ЗАПУСКА ПРИЛОЖЕНИЯ (в другом терминале):
idevicesyslog 2>&1 | tee ~/Downloads/Blender3GS-ui41-device.log | grep --line-buffered -E 'Blender3GS UI41 MEGA|Blender3GS UI40 FAST|Blender3GS UI31 PY|Blender3GS UI17 PROPERTIES|Blender3GS UI28 LIFE|jetsam|watchdog'

Сравниваем timestamp первой UI40 FAST native_frame_done с временем
входа в Blender. Лог UI41 MEGA bbox_preview_begin подтверждает, что
используется реальная облегчённая Viewport-отрисовка. Если время не
сократилось, значит стоимость первого кадра не связана с drawtype,
и это направление откатываем без новых слепых упрощений.
