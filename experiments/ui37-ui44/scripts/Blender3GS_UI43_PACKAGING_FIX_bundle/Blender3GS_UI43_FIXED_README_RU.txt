Blender3GS UI43 — ИСПРАВЛЕНИЕ УПАКОВЩИКА ПОСЛЕ УСПЕШНОЙ КОМПИЛЯЦИИ

Ошибка `STOP: packaged binary incorrect or unchanged` в исходном UI43 возникла
из-за сравнения SHA256 неподписанного ~/Downloads/Blender3GS-python-armv7
с SHA256 подписанного `ldid -S` бинарника ВНУТРИ IPA. ldid закономерно меняет
байты Mach-O, поэтому хеши различаются даже при правильной сборке.

На основании присланного вывода UI43 уже применил патчи, скомпилировал все три
цели, перелинковал ARMv7 и прошел lipo. Сбой был только после подписи/упаковки.

НА ТВОЕМ МАКЕ НЕ ЗАПУСКАЙ СНОВА ОБЫЧНУЮ КОМАНДУ: исходники уже пропатчены.

1. Положи ZIP в ~/Downloads и исполни:
   cd ~/Downloads && unzip -o Blender3GS_UI43_PACKAGING_FIX_bundle.zip -d ~/Downloads && bash Blender3GS_UI43_FIXED_BUILD_INSTALL.command --package-only

Скрипт проверяет все три существующие резервные копии и соответствующие
пропатченные исходники, лог успешной проверки ARMv7, наличие четырех UI43
маркеров в перелинкованном бинарнике, затем переподписывает ЕГО КОПИЮ во
временном каталоге, сверяет IPA с ПОДПИСАННЫМ бинарником и устанавливает через
ideviceinstaller по USB. Исходники, линкованный бинарник и UI41 IPA не меняются.

2. Если на Маке не сохранилась компиляция или отсутствуют UI43 маркеры:
   cd ~/Downloads && bash Blender3GS_UI43_FIXED_BUILD_INSTALL.command --resume

3. Если уже создалась итоговая IPA, нужна только установка:
   cd ~/Downloads && bash Blender3GS_UI43_FIXED_BUILD_INSTALL.command --install-only

4. Откат установленной программы на UI41:
   cd ~/Downloads && bash Blender3GS_UI43_FIXED_BUILD_INSTALL.command --rollback

5. Логи устройства:
   idevicesyslog 2>&1 | tee ~/Downloads/Blender3GS-ui43-device.log | grep --line-buffered -E 'Blender3GS UI43 VIS|Blender3GS UI40 FAST|Blender3GS UI17 PROPERTIES'

Обновлённый алгоритм различает неподписанный, подписанный и упакованный SHA256.
Тест локально моделирует ldid, меняющий байты, и проверяет сохранность Python,
списка файлов, версии и CRC. Физический iPhone и Xcode на сервере недоступны.

UI43 намеренно скрывает только геометрию Camera/Lamp в Viewport для диагностики.
Сами объекты остаются в сцене и Outliner; это эксперимент, не окончательный фикс.
