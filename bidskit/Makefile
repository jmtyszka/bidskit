app_name = bidskit
app_py = $(app_name).py
ui_py = $(app_name)_ui.py
ui_qt = $(app_name).ui

all: $(ui_py)

$(ui_py): $(ui_qt)
	pyside2-uic -x $< -o $@

clean:
	rm -rf $(ui_py)
