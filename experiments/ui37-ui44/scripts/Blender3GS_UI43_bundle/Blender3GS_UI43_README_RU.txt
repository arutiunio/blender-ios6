Blender3GS UI43 VISUAL DIAGNOSTIC — экспериментальный нативный патч поверх UI41.

Цели: изолировать белый треугольник/большую рамку от служебной геометрии
Camera/Lamp, вернуть штатное затенение уже на первом кадре, показать встроенные
16x16 bitmap-иконки без проблемного glDrawPixels и гигантского atlas 1024x1024.

Сцена, данные Camera/Lamp, рендер, Outliner, сохранение, CPU picking не удаляются.
Однако сами объекты Camera/Lamp намеренно НЕ РИСУЮТСЯ во Viewport в этой
диагностической версии (и обычное графическое выделение этих двух типов может
измениться); управлять ими можно через Outliner. Это не окончательная реализация
заменяющих линий, а A/B-тест причины белых полигонов.

Сохраняются ранний C Viewport UI40/41, поздний Python, Core-профиль UI39.
Никаких изменений Python-пейлоада по сравнению с UI41.

1) Скачать ZIP в ~/Downloads. На Mac USB iPhone 3GS:
   cd ~/Downloads && unzip -o Blender3GS_UI43_bundle.zip -d ~/Downloads && bash Blender3GS_UI43_BUILD_INSTALL.command
2) Перед изменением исходников проверить:
   cd ~/Downloads && bash Blender3GS_UI43_BUILD_INSTALL.command --check-only
3) Если сборка упала ПОСЛЕ строк BACKUP + PATCH:
   cd ~/Downloads && bash Blender3GS_UI43_BUILD_INSTALL.command --resume
4) Только установка уже готовой IPA:
   cd ~/Downloads && bash Blender3GS_UI43_BUILD_INSTALL.command --install-only
5) Восстановить установленную UI41 (исходники остаются патчены UI43):
   cd ~/Downloads && bash Blender3GS_UI43_BUILD_INSTALL.command --rollback
6) Лог:
   idevicesyslog 2>&1 | tee ~/Downloads/Blender3GS-ui43-device.log | grep --line-buffered -E 'Blender3GS UI43 VIS|Blender3GS UI40 FAST|Blender3GS UI37 ICON|Blender3GS UI31 PY|Blender3GS UI17 PROPERTIES'

Особенно важны: camera_viewport_helper_skipped / lamp_viewport_helper_skipped,
tiny_icon_texture_ok либо tiny_icon_texture_error и фото после полной загрузки.
Если белые полигоны остались при скрытых Camera/Lamp — их причина не в этих
объектах, и нужно искать draw stack/GL state или geometry Mesh.

Без Mac-компиляции здесь: скрипт сверяет на Mac реальные исходники, оставляет
резервные копии и отказывается менять незнакомое состояние. Ни пиксельного
результата, ни исправления бага на физическом устройстве до теста не обещаем.
