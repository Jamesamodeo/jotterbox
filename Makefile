Jotterbox:
	pyinstaller --noconfirm --log-level=WARN \
	--noconsole \
	--add-data="Jotterbox.ico;." \
	--hidden-import=babel.numbers \
	--icon=Jotterbox.ico \
	Jotterbox.py