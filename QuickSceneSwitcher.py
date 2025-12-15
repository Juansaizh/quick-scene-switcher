"""
  ========================================================================
  SCRIPT: QuickSceneSwitcher
  VERSION: 1.0.0
  AUTHOR: Juan Saiz Huerta
  COPYRIGHT: (c) 2025 Juan Saiz Huerta
  LICENSE: MIT License
  REPOSITORY: https://github.com/juansaizh/quick-scene-switcher
  ========================================================================

  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
  SOFTWARE.

"""

import sys
import os
import uuid
from PySide2 import QtWidgets, QtGui, QtCore

try:
    import pymxs
    rt = pymxs.runtime
    MAX_AVAILABLE = True
except ImportError:
    MAX_AVAILABLE = False

try:
    import qtmax
    HAS_QTMAX = True
except ImportError:
    HAS_QTMAX = False

def get_icon(max_name, fallback_standard_icon_attr=None, style=None):
    """
    Intenta cargar un icono nativo de Max (debug enabled).
    Si falla y no hay fallback, devuelve QIcon nulo.
    """
    icon = None
    if HAS_QTMAX:
        try:
             icon = qtmax.GetQIcon(max_name)
             if icon and not icon.isNull():
                 return icon
        except:
             pass

        path_name = max_name if "/" in max_name else f"MainUI/{max_name}"
        try:
            icon = qtmax.LoadMaxMultiResIcon(path_name)
            if icon and not icon.isNull():
                 return icon
        except:
            pass

    if style and fallback_standard_icon_attr is not None:
        return style.standardIcon(fallback_standard_icon_attr)

    return QtGui.QIcon()

class SceneSwitcherUI(QtWidgets.QDockWidget):
    def __init__(self, parent=None):
        if MAX_AVAILABLE and parent is None:
            parent = QtWidgets.QWidget.find(rt.windows.getMAXHWND())
        super(SceneSwitcherUI, self).__init__(parent)

        self.setWindowTitle("Quick Scene Switcher")
        self.resize(350, 500)
        self.current_scene_path = ""

        self.setObjectName("SceneSwitcherDock")
        self.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        self.main_widget = QtWidgets.QWidget()
        self.setWidget(self.main_widget)

        self.init_ui()
        self.apply_styles()

    def closeEvent(self, event):
        if hasattr(self, 'dirty_timer'):
            self.dirty_timer.stop()
        event.accept()

    def init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self.main_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        self.disable_detection_cb = QtWidgets.QCheckBox("Disable changes detection (faster)")
        self.disable_detection_cb.setChecked(False)
        self.disable_detection_cb.stateChanged.connect(self.check_dirty_status)
        main_layout.addWidget(self.disable_detection_cb)

        folder_layout = QtWidgets.QHBoxLayout()
        folder_layout.setSpacing(5)

        path_container_layout = QtWidgets.QVBoxLayout()
        path_container_layout.setSpacing(2)

        path_input_layout = QtWidgets.QHBoxLayout()
        self.path_le = QtWidgets.QLineEdit()
        self.path_le.setReadOnly(True)
        self.path_le.setPlaceholderText("Select scene folder...")

        self.browse_btn = QtWidgets.QPushButton()
        icon_dir = get_icon("Common/Folder", QtWidgets.QStyle.SP_DirIcon, self.style())
        self.browse_btn.setIcon(icon_dir)
        self.browse_btn.setFixedSize(30, 30)
        self.browse_btn.clicked.connect(self.browse_folder)

        path_input_layout.addWidget(self.path_le)
        path_input_layout.addWidget(self.browse_btn)

        path_container_layout.addLayout(path_input_layout)
        main_layout.addLayout(path_container_layout)

        self.folder_name_label = QtWidgets.QLabel("")
        self.folder_name_label.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 15px; margin-top: 3px; margin-bottom: 3px;")
        main_layout.addWidget(self.folder_name_label)

        self.scene_list = QtWidgets.QListWidget()
        self.scene_list.setAlternatingRowColors(True)
        self.scene_list.itemDoubleClicked.connect(self.switch_to_scene_layer)
        main_layout.addWidget(self.scene_list)

        action_layout = QtWidgets.QHBoxLayout()

        icon_save = get_icon("Common/Save", None, self.style())
        icon_copy = get_icon("Common/Copy", None, self.style())
        icon_paste = get_icon("Common/Paste", None, self.style())

        self.save_btn = QtWidgets.QPushButton(" Save")
        self.save_btn.setIcon(icon_save)
        self.save_btn.setIconSize(QtCore.QSize(16,16))
        self.save_btn.setFixedHeight(35)
        self.save_btn.setToolTip("Save the current scene (layer) back to its file")
        self.save_btn.clicked.connect(self.action_save_selected)

        self.copy_btn = QtWidgets.QPushButton(" Copy")
        self.copy_btn.setIcon(icon_copy)
        self.copy_btn.setIconSize(QtCore.QSize(16,16))
        self.copy_btn.setFixedHeight(35)
        self.copy_btn.clicked.connect(self.action_copy)

        self.paste_btn = QtWidgets.QPushButton(" Paste")
        self.paste_btn.setIcon(icon_paste)
        self.paste_btn.setIconSize(QtCore.QSize(16,16))
        self.paste_btn.setFixedHeight(35)
        self.paste_btn.clicked.connect(self.action_paste)

        action_layout.addWidget(self.save_btn)
        action_layout.addWidget(self.copy_btn)
        action_layout.addWidget(self.paste_btn)

        main_layout.addLayout(action_layout)

        self.active_scene_item = None

        self.dirty_timer = QtCore.QTimer(self)
        self.dirty_timer = QtCore.QTimer(self)
        self.dirty_timer.timeout.connect(self.check_modifications)
        self.dirty_timer.start(500)

        self.is_ui_dirty = False

        self.file_timestamps = {}

        if not self.dirty_timer.isActive():
            self.dirty_timer.start(500)

    def check_modifications(self):
        """Wrapper to check both internal dirty state and external file changes."""
        self.check_dirty_status()
        self.check_external_changes()

    def check_external_changes(self):
        """
        Revisa si el archivo de la escena activa ha sido modificado externamente.
        Si la fecha del archivo en disco > fecha guardada -> Alerta.
        """
        if not self.active_scene_item:
            return

        full_path = self.active_scene_item.data(QtCore.Qt.UserRole)
        if full_path not in self.file_timestamps:
            return

        try:
            current_mtime = os.path.getmtime(full_path)
            last_mtime = self.file_timestamps[full_path]

            if current_mtime > last_mtime:
                self.dirty_timer.stop()

                msg_box = QtWidgets.QMessageBox(self)
                msg_box.setWindowTitle("The scene has been modified externally")
                msg_box.setText(f"The following scene has been changed:\n\n'{os.path.basename(full_path)}'\n\n"
                                "Do you want to reload the scene?")

                btn_reload = msg_box.addButton("Reload", QtWidgets.QMessageBox.AcceptRole)
                btn_ignore = msg_box.addButton("Ignore", QtWidgets.QMessageBox.RejectRole)

                btn_reload.setStyleSheet("""
                    background-color: #1e9bfd;
                    color: white;
                    border: 1px solid #1e9bfd;
                    border-radius: 3px;
                    padding: 5px 15px;
                """)
                btn_ignore.setStyleSheet("padding: 5px 15px;")

                msg_box.exec_()

                if msg_box.clickedButton() == btn_reload:
                    self.reload_active_scene()
                else:
                    self.file_timestamps[full_path] = current_mtime
                    self.dirty_timer.start(500)

        except Exception as e:
            if not self.dirty_timer.isActive():
                self.dirty_timer.start(500)

    def reload_active_scene(self):
        """
        Reloads ONLY the active scene (Layer).
        1. Delete objects in active layer hierarchy.
        2. Re-import file.
        3. Restore state.
        """
        if not self.active_scene_item:
            self.dirty_timer.start(500)
            return

        full_path = self.active_scene_item.data(QtCore.Qt.UserRole)
        display_name = self.active_scene_item.data(QtCore.Qt.UserRole + 1)

        index = self.scene_list.row(self.active_scene_item)

        if MAX_AVAILABLE:
            rt.disableRefMsgs()

            try:
                root_layer = rt.LayerManager.getLayerFromName(display_name)

                if root_layer:
                    all_layers_cache = []
                    for i in range(rt.LayerManager.count):
                        all_layers_cache.append(rt.LayerManager.getLayer(i))

                    def get_children(parent_name):
                        children = []
                        for lyr in all_layers_cache:
                            p = lyr.getParent()
                            if p and p.name == parent_name:
                                children.append(lyr)
                        return children

                    def collect_layers_recursive(parent_lyr):
                        desc = [parent_lyr]
                        subdir = get_children(parent_lyr.name)
                        for child in subdir:
                            desc.extend(collect_layers_recursive(child))
                        return desc

                    layers_to_clean = collect_layers_recursive(root_layer)
                    valid_names = set(l.name for l in layers_to_clean)

                    objs_to_delete = []
                    for obj in rt.objects:
                        if obj.layer.name in valid_names:
                            objs_to_delete.append(obj)

                    if objs_to_delete:
                        rt.delete(objs_to_delete)

                    for lyr in reversed(layers_to_clean):
                        try:
                             rt.LayerManager.deleteLayerByName(lyr.name)
                        except:
                             pass

                self.import_single_scene(full_path, index, is_reload=True)

            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Reload Error", str(e))

            finally:
                rt.enableRefMsgs()
                rt.redrawViews()

        else:
             try:
                self.file_timestamps[full_path] = os.path.getmtime(full_path)
             except: pass

        self.dirty_timer.start(500)

    def check_dirty_status(self):
        """Revisa si la escena de Max necesita guardado y actualiza la UI."""
        if not self.active_scene_item:
            return

        is_dirty = False
        if MAX_AVAILABLE:
            is_dirty = rt.getSaveRequired()

        if is_dirty != self.is_ui_dirty:
            self.set_item_dirty(self.active_scene_item, is_dirty)
            self.is_ui_dirty = is_dirty

    def set_item_dirty(self, item, dirty):
        """Añade o quita el asterisco del nombre."""
        text = item.text()
        if dirty:
            if not text.endswith("*"):
                item.setText(text + "*")
        else:
            if text.endswith("*"):
                item.setText(text.rstrip("*"))

    def apply_styles(self):
        qss = """
        QWidget {
            background-color: #444444; /* Fondo base oscuro */
            color: #ffffff;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 13px;
        }
        QDialog, QDockWidget {
            background-color: #444444;
            border: 1px solid #333;
        }
        QLabel {
            color: #ffffff;
        }
        QLineEdit {
            border: 1px solid #444;
            background-color: #646464;
            border-radius: 3px;
            padding: 4px 8px;
            color: #ffffff;
        }
        QPushButton {
            background-color: #646464;
            border: 1px solid #555;
            border-radius: 3px;
            padding: 5px;
            color: #ffffff;
        }
        QPushButton:hover {
            background-color: #707070;
            border-color: #888;
        }
        QPushButton:pressed {
            background-color: #505050;
        }
        QListWidget {
            border: 1px solid #383838;
            background-color: #444444;
            border-radius: 3px;
            outline: none;
            color: #ffffff;
        }
        QListWidget::item {
            padding: 8px 10px;
            color: #ffffff;
            border-bottom: 1px solid #3d3d3d;
        }
        QListWidget::item:alternate {
            background-color: #5a5a5a;
        }
        QListWidget::item:selected {
            background-color: #1e9bfd; /* Azul estándar selección */
            color: #ffffff;
            border: none;
        }
        QListWidget::item:hover:!selected {
            background-color: #606060;
        }
        QCheckBox {
            color: #ffffff;
            spacing: 5px;
        }
        QCheckBox::indicator {
            width: 14px;
            height: 14px;
            background-color: #646464; /* Unchecked background */
            border: 1px solid #444;    /* Border requested */
            border-radius: 8px;
        }
        QCheckBox::indicator:hover {
            border-color: #888;
            background-color: #707070;
        }
        QCheckBox::indicator:checked {
            width: 6px;
            height: 6px;
            background-color: #474747; /* Blue when checked */
            border: 5px solid #d4d4d4;
        }
        """
        self.setStyleSheet(qss)

        action_btn_style = """
        QPushButton {
            background-color: #646464;
            border: 1px solid #555;
            color: #ffffff;
        }
        QPushButton:hover {
             background-color: #383838;
             border: 1px solid #999;
        }
        """
        self.copy_btn.setStyleSheet(action_btn_style)
        self.paste_btn.setStyleSheet(action_btn_style)
        self.save_btn.setStyleSheet(action_btn_style)

    def browse_folder(self):
        """Abre el explorador, selecciona archivos .max y comienza el Merge Process."""
        start_dir = self.path_le.text() if self.path_le.text() else os.path.expanduser("~")

        files, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "Select Scene Files", start_dir, "Max Scenes (*.max)")

        if files:
            folder_path = os.path.dirname(files[0])
            self.path_le.setText(folder_path)

            self.merge_all_scenes(folder_path, file_list=files)


    def merge_all_scenes(self, folder_path, file_list=None):
        """
        Merge Process:
        1. Create Root Layer (Scene Name).
        2. Merge File.
        3. Identify Imported Layers -> Rename to 'Name (Scene)' -> Parent to Root.
        4. Identify Collisions -> Move objects to new 'Name (Scene)' layer -> Parent to Root.
        """
        self.dirty_timer.stop()

        self.folder_name_label.setText(os.path.basename(folder_path))

        max_files = []
        try:
            if file_list:
                max_files = file_list
            else:
                for f in os.listdir(folder_path):
                    if f.lower().endswith(".max"):
                        max_files.append(os.path.join(folder_path, f))
                max_files.sort()

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Could not scan files:\n{e}")
            self.dirty_timer.start(500)
            return

        if not max_files:
            QtWidgets.QMessageBox.information(self, "Info", "No .max files found in folder.")
            self.dirty_timer.start(500)
            return

        if MAX_AVAILABLE:
            rt.resetMaxFile(quiet=True)
            rt.setSaveRequired(False)

        self.scene_list.clear()

        self.scene_list.clear()
        self.file_timestamps = {}

        for index, full_path in enumerate(max_files):
             self.import_single_scene(full_path, index, is_reload=False)

        if MAX_AVAILABLE:
            rt.clearSelection()
            rt.redrawViews()
            self.clean_up_material_names()

        QtCore.QTimer.singleShot(200, lambda: self.force_clean_and_restart_timer(use_temp_save=False))

    def generate_unique_suffix(self):
        return f".Duplicate.{uuid.uuid4().hex[:8]}"

    def clean_up_material_names(self):
        """
        Removes the .Duplicate.HASH suffix from all materials in the scene.
        """
        if not MAX_AVAILABLE:
            return

        duplicates_cleaned = 0
        # Iterate over all scene materials
        # rt.sceneMaterials includes all materials used in the scene
        for mat in rt.sceneMaterials:
            mat_name = mat.name
            if ".Duplicate." in mat_name:
                # Find the index of the suffix
                split_name = mat_name.split(".Duplicate.")
                original_name = split_name[0]
                
                # Rename back to original
                # Since Max allows duplicate names, this is safe and desired
                try:
                    mat.name = original_name
                    duplicates_cleaned += 1
                except:
                    pass
        
        print(f"Cleaned up {duplicates_cleaned} duplicate material names.")

    def import_single_scene(self, full_path, index=0, is_reload=False):
        """
        Imports a SINGLE scene file into the hierarchy.
        Used by merge_all_scenes and also for Reloading.
        """
        full_path = str(full_path).replace("\\", "/")
        file_name = os.path.basename(full_path)
        display_name = os.path.splitext(file_name)[0]

        try:
            self.file_timestamps[full_path] = os.path.getmtime(full_path)
        except:
            pass

        if MAX_AVAILABLE:
            scene_root_layer = rt.LayerManager.getLayerFromName(display_name)
            if not scene_root_layer:
                scene_root_layer = rt.LayerManager.newLayerFromName(display_name)

            scene_root_layer.current = True

            existing_layer_names = set()
            for i in range(rt.LayerManager.count):
                existing_layer_names.add(rt.LayerManager.getLayer(i).name)

            rt.mergeMaxFile(full_path, rt.name("mergeDups"), rt.name("select"), quiet=True)
            
            # --- UNIQUE MATERIAL RENAMING START ---
            # To prevent name collisions during subsequent merges, we give unique names
            # to the materials of the newly merged objects.
            unique_suffix = self.generate_unique_suffix()
            
            # Helper to recursively get materials from an object
            def get_materials_from_nodes(nodes):
                mats = set()
                for obj in nodes:
                    if obj.material:
                        mats.add(obj.material)
                return mats

            merged_objects = list(rt.selection)
            merged_materials = get_materials_from_nodes(merged_objects)
            
            for mat in merged_materials:
                # Append unique suffix
                # e.g. "Wood" -> "Wood.Duplicate.a1b2c3d4"
                try:
                    mat.name = f"{mat.name}{unique_suffix}"
                except:
                    pass
            # --- UNIQUE MATERIAL RENAMING END ---

            suffix = f" ({display_name})"

            objs_on_layer_0 = [x for x in rt.selection if x.layer.name == "0"]
            if objs_on_layer_0:
                layer0_name = f"0{suffix}"
                layer0_scene = rt.LayerManager.getLayerFromName(layer0_name)
                if not layer0_scene:
                    layer0_scene = rt.LayerManager.newLayerFromName(layer0_name)

                layer0_scene.setParent(scene_root_layer)
                for obj in objs_on_layer_0:
                    layer0_scene.addNode(obj)

            all_layers = []
            for i in range(rt.LayerManager.count):
                all_layers.append(rt.LayerManager.getLayer(i))

            new_layers_set = set()
            created_layer0_name = f"0{suffix}"

            for layer in all_layers:
                if layer.name == "0" or layer.name == display_name:
                        continue
                if layer.name == created_layer0_name:
                        continue

                if layer.name not in existing_layer_names:
                        new_layers_set.add(layer)

            for layer in list(new_layers_set):
                old_name = layer.name
                new_name = f"{old_name}{suffix}"

                layer.setName(new_name)

                parent = layer.getParent()

                is_nested = False
                if parent:
                    if parent in new_layers_set:
                        is_nested = True

                if not is_nested:
                    layer.setParent(scene_root_layer)

            for layer_name in existing_layer_names:
                if layer_name == "0": continue

                objs_in_layer = [x for x in rt.selection if x.layer.name == layer_name]
                if objs_in_layer:
                    unique_name = f"{layer_name}{suffix}"
                    unique_layer = rt.LayerManager.getLayerFromName(unique_name)
                    if not unique_layer:
                            unique_layer = rt.LayerManager.newLayerFromName(unique_name)
                            unique_layer.setParent(scene_root_layer)

                    for obj in objs_in_layer:
                        unique_layer.addNode(obj)

            if not is_reload:
                should_be_visible = (index == 0)
                scene_root_layer.on = should_be_visible

        icon_item = None
        if MAX_AVAILABLE:
            try:
                max_root = rt.getDir(rt.name("maxroot"))
                custom_icon_path = os.path.join(max_root, "UI_ln", "IconsDark", "ATS", "ATSScene.ico")
                if os.path.exists(custom_icon_path):
                        icon_item = QtGui.QIcon(custom_icon_path)
            except:
                pass

        if not icon_item or icon_item.isNull():
                icon_item = get_icon("Citras/3dsMax", QtWidgets.QStyle.SP_FileIcon, self.style())

        if not is_reload:
            item = QtWidgets.QListWidgetItem(icon_item, display_name)
            item.setData(QtCore.Qt.UserRole, full_path)
            item.setData(QtCore.Qt.UserRole + 1, display_name)
            self.scene_list.addItem(item)

            if index == 0:
                self.active_scene_item = item
                self.highlight_item(item, True)
            else:
                self.highlight_item(item, False)


    def switch_to_scene_layer(self, item):
        """
        Al hacer doble click:
        1. Verifica cambios sin guardar.
        2. Oculta TODAS las capas de la lista.
        3. Muestra SOLO la capa asociada al item clickado.
        4. Actualiza UI (negrita).
        """
        if item == self.active_scene_item:
            return

        self.dirty_timer.stop()

        if not self.check_unsaved_changes():
            self.dirty_timer.start(500)
            return

        tgt_layer_name = item.data(QtCore.Qt.UserRole + 1)
        self.active_scene_item = item

        if MAX_AVAILABLE:
            rt.clearSelection()
            count = self.scene_list.count()
            for i in range(count):
                list_item = self.scene_list.item(i)
                layer_name = list_item.data(QtCore.Qt.UserRole + 1)

                layer = rt.LayerManager.getLayerFromName(layer_name)
                if layer:
                    if layer_name == tgt_layer_name:
                        layer.on = True
                        layer.current = True
                    else:
                        layer.on = False

            rt.redrawViews()

            for i in range(self.scene_list.count()):
                 self.set_item_dirty(self.scene_list.item(i), False)

        self.update_list_highlights()

        QtCore.QTimer.singleShot(200, lambda: self.force_clean_and_restart_timer(use_temp_save=False))

    def force_clean_and_restart_timer(self, use_temp_save=False):
        """
        Fuerza el estado 'limpio' en Max y reinicia el timer.

        Args:
            use_temp_save (bool): Si True, guarda escena a un archivo temporal.
                                  Esto es más lento pero mucho más robusto para
                                  limpiar flags persistentes tras modificaciones reales.
                                  Si False, usa un reset ligero (setSaveRequired) para switches rápidos.
        """
        if MAX_AVAILABLE:
            try:
                should_save_temp = use_temp_save
                if hasattr(self, 'disable_detection_cb') and self.disable_detection_cb.isChecked():
                    should_save_temp = False

                if should_save_temp:
                    temp_dir = rt.getdir(rt.name("temp"))
                    temp_file = os.path.join(temp_dir, "SceneSwitcher_Master_Reset.max")
                    rt.saveMaxFile(temp_file, quiet=True)

                rt.setSaveRequired(False)

                if self.active_scene_item:
                    self.set_item_dirty(self.active_scene_item, False)
                self.is_ui_dirty = False

            except Exception as e:
                pass

        if not self.dirty_timer.isActive():
            self.dirty_timer.start(500)

    def check_dirty_status(self):
        """Revisa si la escena de Max necesita guardado y actualiza la UI."""
        if not self.active_scene_item:
            return

        if hasattr(self, 'disable_detection_cb') and self.disable_detection_cb.isChecked():
            if self.is_ui_dirty:
                self.set_item_dirty(self.active_scene_item, False)
                self.is_ui_dirty = False
            return

        is_dirty = False
        if MAX_AVAILABLE:
            try:
                is_dirty = rt.getSaveRequired()
            except:
                return

        if is_dirty != self.is_ui_dirty:
            self.set_item_dirty(self.active_scene_item, is_dirty)
            self.is_ui_dirty = is_dirty

    def check_unsaved_changes(self):
        """
        Muestra diálogo personalizado si hay cambios.
        Returns:
            True si se puede proceder (Save o Don't Save).
            False si se cancela.
        """
        if hasattr(self, 'disable_detection_cb') and self.disable_detection_cb.isChecked():
             return True

        if MAX_AVAILABLE and rt.getSaveRequired():
            active_path = self.active_scene_item.data(QtCore.Qt.UserRole)

            msg_text = (f"Do you want to save the changes you made in the scene:\n\n"
                        f"{active_path}")

            msg_box = QtWidgets.QMessageBox(self)
            msg_box.setWindowTitle("Scene has been modified")
            msg_box.setText(msg_text)

            btn_save = msg_box.addButton("Save", QtWidgets.QMessageBox.AcceptRole)
            btn_dont_save = msg_box.addButton("Don't Save", QtWidgets.QMessageBox.DestructiveRole)
            btn_cancel = msg_box.addButton("Cancel", QtWidgets.QMessageBox.RejectRole)

            btn_save.setStyleSheet("""
                background-color: #1e9bfd;
                color: white;
                border: 1px solid #1e9bfd;
                border-radius: 3px;
                padding: 5px 25px; /* Larger padding */
                font-weight: bold;
            """)

            btn_dont_save.setStyleSheet("padding: 5px 15px;")
            btn_cancel.setStyleSheet("padding: 5px 15px;")

            msg_box.exec_()

            clicked_button = msg_box.clickedButton()

            if clicked_button == btn_save:
                saved = self.action_save_selected()
                return saved
            elif clicked_button == btn_dont_save:
                QtCore.QTimer.singleShot(100, lambda: self.force_clean_and_restart_timer(use_temp_save=True))
                return True
            else:
                return False

        return True

    def update_list_highlights(self):
        """Pone en negrita el activo, normal el resto."""
        font_normal = QtGui.QFont()
        font_normal.setBold(False)
        font_bold = QtGui.QFont()
        font_bold.setBold(True)

        for i in range(self.scene_list.count()):
            item = self.scene_list.item(i)
            if item == self.active_scene_item:
                item.setFont(font_bold)
            else:
                item.setFont(font_normal)

    def highlight_item(self, item, bold):
        """Ayuda simple para negrita."""
        f = item.font()
        f.setBold(bold)
        item.setFont(f)

    def action_save_selected(self):
        """
        Saves the active hierarchy (Root + Children).
        Transient Renaming Logic:
        1. Identify child layers.
        2. Strip suffix ' (SceneName)' temporarily.
        3. Save nodes.
        4. Restore suffix.
        """
        if not self.active_scene_item:
            QtWidgets.QMessageBox.warning(self, "Warning", "No active scene.")
            return False

        self.dirty_timer.stop()

        target_file = self.active_scene_item.data(QtCore.Qt.UserRole)
        layer_name = self.active_scene_item.data(QtCore.Qt.UserRole + 1)

        display_name = os.path.splitext(os.path.basename(target_file))[0]
        suffix = f" ({display_name})"

        save_success = False

        if MAX_AVAILABLE:
            user_selection = list(rt.selection)
            selection_was_empty = (len(user_selection) == 0)

            root_layer = rt.LayerManager.getLayerFromName(layer_name)
            if not root_layer:
                QtWidgets.QMessageBox.warning(self, "Error", f"Root Layer '{layer_name}' not found!")
                self.dirty_timer.start(500)
                return False

            all_layers_cache = []
            for i in range(rt.LayerManager.count):
                all_layers_cache.append(rt.LayerManager.getLayer(i))

            state_map = {}

            def get_children_from_cache(parent_name):
                children = []
                for lyr in all_layers_cache:
                    p = lyr.getParent()
                    if p and p.name == parent_name:
                         children.append(lyr)
                return children

            def collect_descendants_recursive(parent_lyr):
                desc_list = []
                direct_children = get_children_from_cache(parent_lyr.name)
                for child in direct_children:
                    desc_list.append(child)
                    desc_list.extend(collect_descendants_recursive(child))
                return desc_list

            descendants = collect_descendants_recursive(root_layer)

            valid_layer_names = set()
            valid_layer_names.add(root_layer.name)
            for l in descendants:
                valid_layer_names.add(l.name)

            nodes_to_save = []

            for obj in rt.objects:
                if obj.layer.name in valid_layer_names:
                    nodes_to_save.append(obj)

            layer0_sub_name = f"0{suffix}"
            moved_nodes_restore_map = {}

            global_layer_0 = rt.LayerManager.getLayer(0)

            for obj in nodes_to_save:
                current_layer_name = obj.layer.name

                if current_layer_name == layer0_sub_name:
                    moved_nodes_restore_map[obj] = obj.layer

                elif current_layer_name == layer_name:
                     moved_nodes_restore_map[obj] = obj.layer

            if moved_nodes_restore_map:
                for obj in moved_nodes_restore_map.keys():
                    global_layer_0.addNode(obj)

            for layer in descendants:
                original_name = layer.name
                original_parent = layer.getParent()

                state_map[layer] = {'name': original_name, 'parent': original_parent}

                if original_name.endswith(suffix):
                    clean_name = original_name[:-len(suffix)]

                    if clean_name == "0":
                        continue

                    try:
                        layer.setName(clean_name)
                    except:
                        pass

                if original_parent and original_parent.name == root_layer.name:
                    try:
                        layer.setParent(rt.undefined)
                    except:
                        pass

            rt.clearSelection()

            if nodes_to_save:
                try:
                    rt.select(nodes_to_save)
                except Exception as e:
                    pass

            final_selection = rt.selection
            count_sel = final_selection.count

            if count_sel > 0:
                result = rt.saveNodes(final_selection, target_file, quiet=True)
                save_success = True

            for layer, state in state_map.items():
                try:
                    if state['parent']:
                        layer.setParent(state['parent'])

                    if layer.name != state['name']:
                        layer.setName(state['name'])
                except Exception as e:
                    pass

            for obj, original_layer in moved_nodes_restore_map.items():
                try:
                    original_layer.addNode(obj)
                except Exception as e:
                    pass

            rt.clearSelection()
            if not selection_was_empty:
                try:
                    rt.select(user_selection)
                except: pass

            rt.enableRefMsgs()
            rt.redrawViews()

        if save_success:
            try:
                self.file_timestamps[target_file] = os.path.getmtime(target_file)
            except:
                pass
            QtCore.QTimer.singleShot(200, lambda: self.force_clean_and_restart_timer(use_temp_save=True))
            return True

        QtCore.QTimer.singleShot(200, lambda: self.force_clean_and_restart_timer(use_temp_save=True))
        return False

    def action_copy(self):
        if MAX_AVAILABLE:
            selection = rt.selection
            if selection.count > 0:
                temp_path = os.path.join(rt.getdir(rt.name("temp")), "temp_clipboard.max")
                rt.saveNodes(selection, temp_path, quiet=True)

    def action_paste(self):
        if MAX_AVAILABLE:
            temp_path = os.path.join(rt.getdir(rt.name("temp")), "temp_clipboard.max")
            if os.path.exists(temp_path):
                rt.mergeMaxFile(temp_path, rt.name("mergeDups"), rt.name("select"), quiet=True)

                if self.active_scene_item:
                    layer_name = self.active_scene_item.data(QtCore.Qt.UserRole + 1)
                    layer = rt.LayerManager.getLayerFromName(layer_name)
                    if layer:
                        for node in rt.selection:
                            layer.addNode(node)

def run_max_ui():
    app = QtWidgets.QApplication.instance()
    if not app:
        app = QtWidgets.QApplication(sys.argv)

    for widget in app.topLevelWidgets():
        if widget.objectName() == "SceneSwitcherDock":
            widget.show()
            widget.raise_()
            return

    dock = SceneSwitcherUI()
    if MAX_AVAILABLE:
        dock.setFloating(True)
        dock.show()
    else:
        dock.show()

    return dock

if __name__ == "__main__":
    if MAX_AVAILABLE:
        _scene_switcher_ui_ref = run_max_ui()
    else:
        app = QtWidgets.QApplication(sys.argv)
        dialog = SceneSwitcherUI()
        dialog.show()
        sys.exit(app.exec_())
