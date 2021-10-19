ifeq ($(OS),Windows_NT)
	# Windows
	SEP=;
else
	# Unix
	SEP=:
endif

Jotterbox:
	pyinstaller --noconfirm --log-level=WARN \
	--noconsole \
	--add-data="Jotterbox.ico$(SEP)." \
	--hidden-import=babel.numbers \
	--icon=Jotterbox.ico \
	Jotterbox.pyw

