# -*- coding: utf-8 -*-
"""
========================================================================
SCRIPT: MultiMaterialEditor
VERSION: 1.0.0
AUTHOR: Juan Saiz Huerta
COPYRIGHT: (c) 2026 Juan Saiz Huerta
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

Compatible with 3ds Max 2021, 2022, 2023 (PySide2) and 2024+ (PySide6).
========================================================================
"""

import sys
import os
import time
import math
import copy
import traceback
try:
    import configparser
except ImportError:
    import ConfigParser as configparser

try:
    from PySide2 import QtWidgets, QtCore, QtGui
    from PySide2.QtWidgets import (
        QDialog, QTableWidget, QTableWidgetItem, QVBoxLayout, QHBoxLayout,
        QPushButton, QLabel, QCheckBox, QHeaderView, QAbstractItemView,
        QMessageBox, QFrame, QSplitter, QWidget, QLineEdit, QSpinBox,
        QProgressBar, QToolTip, QColorDialog, QStyledItemDelegate
    )
    from PySide2.QtCore import Qt, QSize, Signal, QPoint, QRect, QRectF, QTimer
    from PySide2.QtGui import QColor, QBrush, QPixmap, QIcon, QPainter, QFont, QPen, QPainterPath
except ImportError:
    from PySide6 import QtWidgets, QtCore, QtGui
    from PySide6.QtWidgets import (
        QDialog, QTableWidget, QTableWidgetItem, QVBoxLayout, QHBoxLayout,
        QPushButton, QLabel, QCheckBox, QHeaderView, QAbstractItemView,
        QMessageBox, QFrame, QSplitter, QWidget, QLineEdit, QSpinBox,
        QProgressBar, QToolTip, QColorDialog, QStyledItemDelegate
    )
    from PySide6.QtCore import Qt, QSize, Signal, QPoint, QRect, QRectF, QTimer
    from PySide6.QtGui import QColor, QBrush, QPixmap, QIcon, QPainter, QFont, QPen, QPainterPath

try:
    import pymxs
    rt = pymxs.runtime
except ImportError:
    rt = None

try:
    import qtmax
    def get_max_main_window():
        return qtmax.GetQMaxMainWindow()
except ImportError:
    def get_max_main_window():
        return None

_CURRENT_JSH_MME_DIALOG = None


def get_lock_icon(is_locked=False):
    """Draws a crisp, vector padlock icon matching the requested design."""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)

    if is_locked:
        # Locked: solid clean white closed padlock with subtle keyhole
        painter.setPen(QPen(QColor("#ffffff"), 1.0))
        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.drawRoundedRect(6, 15, 20, 13, 2, 2)

        # Closed white shackle
        shackle_pen = QPen(QColor("#ffffff"), 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(shackle_pen)
        painter.setBrush(Qt.NoBrush)

        path = QPainterPath()
        path.moveTo(10, 15)
        path.lineTo(10, 10)
        path.arcTo(QRectF(10, 4, 12, 12), 180, -180)
        path.lineTo(22, 15)
        painter.drawPath(path)

        # Keyhole
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor("#2d2d2d")))
        painter.drawEllipse(QPoint(16, 20), 2, 2)
        painter.drawRect(15, 20, 2, 4)
    else:
        # Unlocked: hollow body with matching outline color, open shackle on left side
        pen = QPen(QColor("#c5c5c5"), 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        # Hollow body (no fill, no keyhole)
        painter.drawRoundedRect(6, 15, 20, 13, 2, 2)

        # Open shackle: attached on right, wide opening on left
        path = QPainterPath()
        path.moveTo(21, 15)
        path.lineTo(21, 10)
        path.arcTo(QRectF(9, 3, 12, 12), 0, 120)
        painter.drawPath(path)

    painter.end()
    return QIcon(pixmap)


def get_config_file_path():
    """Returns the path to the MultiMaterialEditor.ini settings file in 3ds Max plugcfg or local directory."""
    try:
        if rt:
            plugcfg_dir = str(rt.getDir(rt.name("plugcfg")))
            if plugcfg_dir and os.path.isdir(plugcfg_dir):
                return os.path.join(plugcfg_dir, "MultiMaterialEditor.ini")
    except Exception:
        pass
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, "MultiMaterialEditor.ini")


def load_config_settings():
    """Loads checkbox and editor preferences from MultiMaterialEditor.ini."""
    ini_path = get_config_file_path()
    settings = {
        'auto_renumber_ids': True,
        'sync_names': True,
        'update_ids_on_geometry': False
    }
    if os.path.isfile(ini_path):
        try:
            config = configparser.ConfigParser()
            config.read(ini_path, encoding='utf-8')
            if config.has_section('Options'):
                if config.has_option('Options', 'auto_renumber_ids'):
                    settings['auto_renumber_ids'] = config.getboolean('Options', 'auto_renumber_ids', fallback=True)
                if config.has_option('Options', 'sync_names'):
                    settings['sync_names'] = config.getboolean('Options', 'sync_names', fallback=True)
                if config.has_option('Options', 'update_ids_on_geometry'):
                    settings['update_ids_on_geometry'] = config.getboolean('Options', 'update_ids_on_geometry', fallback=False)
        except Exception as e:
            print("[MultiMaterialEditor] Error loading INI settings: {}".format(e))
    return settings


def save_config_settings(settings_dict):
    """Saves checkbox and editor preferences to MultiMaterialEditor.ini."""
    ini_path = get_config_file_path()
    try:
        config = configparser.ConfigParser()
        if os.path.isfile(ini_path):
            try:
                config.read(ini_path, encoding='utf-8')
            except Exception:
                pass
        if not config.has_section('Options'):
            config.add_section('Options')
        for key, val in settings_dict.items():
            config.set('Options', str(key), str(val))
        with open(ini_path, 'w', encoding='utf-8') as f:
            config.write(f)
    except Exception as e:
        print("[MultiMaterialEditor] Error saving INI settings: {}".format(e))



def linear_to_srgb_color(r, g, b):
    """Converts linear RGB (0-255) to display sRGB QColor (Gamma 2.2)."""
    if r < 0 or g < 0 or b < 0:
        return None

    def to_display(c_255):
        c = max(0.0, min(255.0, float(c_255))) / 255.0
        s = math.pow(c, 1.0 / 2.2)
        return int(round(max(0.0, min(1.0, s)) * 255.0))

    return QColor(to_display(r), to_display(g), to_display(b))


def srgb_to_linear_rgb(qcolor):
    """Converts display sRGB QColor to linear RGB (0-255) for 3ds Max."""
    if not qcolor or not qcolor.isValid():
        return 0, 0, 0

    def to_linear(s_255):
        s = max(0.0, min(255.0, float(s_255))) / 255.0
        c = math.pow(s, 2.2)
        return int(round(max(0.0, min(1.0, c)) * 255.0))

    return to_linear(qcolor.red()), to_linear(qcolor.green()), to_linear(qcolor.blue())


def get_cached_checkmark_icon_path():
    """Returns the path to the cached checkmark icon for QSS checkboxes."""
    cache_dir = os.path.join(os.path.expanduser("~"), ".jsh_mme_cache")
    if not os.path.exists(cache_dir):
        try:
            os.makedirs(cache_dir)
        except Exception:
            cache_dir = os.environ.get("TEMP", "C:/Temp")

    icon_path = os.path.join(cache_dir, "jsh_mme_white_check.png").replace("\\", "/")
    if not os.path.exists(icon_path):
        try:
            pix = QPixmap(16, 16)
            pix.fill(Qt.transparent)
            painter = QPainter(pix)
            painter.setRenderHint(QPainter.Antialiasing)
            pen = QPen(QColor(255, 255, 255), 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawLine(3, 8, 6, 12)
            painter.drawLine(6, 12, 13, 4)
            painter.end()
            pix.save(icon_path, "PNG")
        except Exception as err:
            print("Error creating checkmark icon: {}".format(err))
    return icon_path


def init_maxscript_helpers():
    """Registers MAXScript helper functions for material and geometry operations."""
    if not rt:
        return
    mxs_code = """
    global _jsh_MME_GetSelectedMaterial
    global _jsh_MME_GetSelectedMultiMaterial
    global _jsh_MME_GetMultiMatData
    global _jsh_MME_ApplyMultiMatData
    global _jsh_MME_SetSubMaterialColor
    global _jsh_MME_UpdateFaceIDs
    global _jsh_MME_UpdateEditPolyFaceIDs
    global _jsh_MME_GetFaceIDCounts
    global _jsh_MME_GetMatFingerprint
    global _jsh_MME_GetMatHandle
    global _jsh_MME_CloneMaterial
    global _jsh_MME_OpenInSME
    global _jsh_MME_SetSlotName
    global _jsh_MME_SetSlotID
    global _jsh_MME_SetSlotEnabled

    fn _jsh_MME_CloneMaterial mat = (
        if mat == undefined or not isValidObj mat do return undefined
        try (
            local newMat = copy mat
            return newMat
        ) catch (
            return undefined
        )
    )

    fn _jsh_MME_OpenInSME subMat = (
        if subMat == undefined or not isValidObj subMat do return false
        try (
            if sme != undefined do (
                if not (sme.isOpen()) do (
                    try ( MatEditor.mode = #slate ) catch()
                    sme.open()
                )
                
                local activeViewIdx = sme.activeView
                if activeViewIdx <= 0 do (
                    if sme.numViews > 0 then (
                        activeViewIdx = 1
                        sme.activeView = 1
                    ) else (
                        activeViewIdx = sme.createView "Materials"
                        sme.activeView = activeViewIdx
                    )
                )
                
                local view = sme.getView activeViewIdx
                if view != undefined do (
                    local targetNode = undefined
                    
                    try (
                        local numN = view.GetNumNodes()
                        for i = 1 to numN do (
                            local n = view.GetNode i
                            if n != undefined and isValidObj n and n.reference == subMat do (
                                targetNode = n
                                exit
                            )
                        )
                    ) catch()
                    
                    if targetNode == undefined do (
                        try (
                            for vIdx = 1 to sme.numViews do (
                                if vIdx != activeViewIdx do (
                                    local v = sme.getView vIdx
                                    if v != undefined do (
                                        local vNumN = v.GetNumNodes()
                                        for j = 1 to vNumN do (
                                            local n = v.GetNode j
                                            if n != undefined and isValidObj n and n.reference == subMat do (
                                                sme.activeView = vIdx
                                                view = v
                                                targetNode = n
                                                exit
                                            )
                                        )
                                    )
                                )
                                if targetNode != undefined do exit
                            )
                        ) catch()
                    )
                    
                    if targetNode == undefined do (
                        try (
                            targetNode = view.createNode subMat [0, 0]
                        ) catch()
                    )
                    
                    if targetNode != undefined do (
                        try ( view.SelectNone() ) catch()
                        try ( targetNode.selected = true ) catch()
                        try (
                            view.ZoomExtents type:#selected
                        ) catch (
                            try ( sme.frameSelected() ) catch()
                        )
                        try ( sme.SetMtlInParamEditor subMat ) catch()
                        return true
                    )
                    try ( sme.SetMtlInParamEditor subMat ) catch()
                )
            )
        ) catch (
            format "Error opening in SME: %\\n" (getCurrentException())
        )
        false
    )

    fn _jsh_MME_GetSelectedMaterial = (
        try (
            if selection != undefined and selection.count > 0 do (
                for obj in selection do (
                    if isValidNode obj and obj.material != undefined and isValidObj obj.material do (
                        return obj.material
                    )
                )
            )
        ) catch()

        try (
            if sme != undefined and sme.isOpen() do (
                local activeViewIdx = sme.activeView
                if activeViewIdx > 0 do (
                    local view = sme.getView activeViewIdx
                    local nodes = view.getSelectedNodes()
                    if nodes != undefined and nodes.count > 0 do (
                        -- Priority 1: MultiMaterial selected or dependent in SME
                        for n in nodes do (
                            local ref = n.reference
                            if ref != undefined and isValidObj ref do (
                                if (isKindOf ref Multimaterial or isKindOf ref multiSubMaterial) do return ref
                                local deps = (refs.dependents ref)
                                for d in deps do (
                                    if isValidObj d and (isKindOf d Multimaterial or isKindOf d multiSubMaterial) do return d
                                )
                            )
                        )
                        -- Priority 2: Any single material selected in SME
                        for n in nodes do (
                            local ref = n.reference
                            if ref != undefined and isValidObj ref and isKindOf ref material do return ref
                        )
                    )
                )
            )
        ) catch()

        try (
            if MatEditor != undefined and MatEditor.isOpen() and MatEditor.mode == #basic do (
                local activeSlot = medit.GetActiveMtlSlot()
                local meditMat = meditMaterials[activeSlot]
                if meditMat != undefined and isValidObj meditMat and (isKindOf meditMat Multimaterial or isKindOf meditMat multiSubMaterial) do (
                    return meditMat
                )
            )
        ) catch()
        
        undefined
    )
    _jsh_MME_GetSelectedMultiMaterial = _jsh_MME_GetSelectedMaterial

    fn _jsh_MME_GetMatHandle mat = (
        if mat == undefined or not isValidObj mat do return 0
        try (
            return (getHandleByAnim mat) as integer
        ) catch (
            return 0
        )
    )

    fn _jsh_MME_GetMatFingerprint mat = (
        try (
            if mat == undefined or not isValidObj mat do return ""
            if not (isKindOf mat Multimaterial or isKindOf mat multiSubMaterial) do (
                return (classOf mat as string) + ":" + (mat.name as string) + ":" + ((getHandleByAnim mat) as string)
            )
            
            -- Read-only check: determine effective slot count ignoring trailing undefined slots with duplicate IDs
            local count = mat.numsubs
            while count > 1 and (count > mat.materialList.count or mat.materialList[count] == undefined or not isValidObj mat.materialList[count]) do (
                local isGhost = false
                local curID = if count <= mat.materialIDList.count then mat.materialIDList[count] else count
                for prev = 1 to (count - 1) do (
                    local prevID = if prev <= mat.materialIDList.count then mat.materialIDList[prev] else prev
                    if curID == prevID do (
                        isGhost = true
                        exit
                    )
                )
                if isGhost then (
                    count -= 1
                ) else (
                    exit
                )
            )

            local fp = (mat.name as string) + "|" + (count as string) + "|"
            for i = 1 to count do (
                local subMat = undefined
                if i <= mat.materialList.count do (
                    try ( subMat = mat.materialList[i] ) catch()
                )
                local hasSub = (subMat != undefined and isValidObj subMat)
                local subAnimHandle = if hasSub then ((getHandleByAnim subMat) as string) else "0"
                local subName = if hasSub then (subMat.name as string) else "(None)"
                local sName = ""
                if i <= mat.names.count and mat.names[i] != undefined do (
                    sName = mat.names[i] as string
                )
                local sID = i
                if i <= mat.materialIDList.count and mat.materialIDList[i] != undefined do (
                    sID = mat.materialIDList[i] as integer
                )
                local sEnabled = true
                if i <= mat.mapEnabled.count and mat.mapEnabled[i] != undefined do (
                    sEnabled = mat.mapEnabled[i] as booleanClass
                )
                
                local colStr = "-1"
                if hasSub do (
                    local col = undefined
                    try (
                        if isProperty subMat #diffuse then col = subMat.diffuse
                        else if isProperty subMat #diffuseColor then col = subMat.diffuseColor
                        else if isProperty subMat #base_color then col = subMat.base_color
                        else if isProperty subMat #baseColor then col = subMat.baseColor
                        else if isProperty subMat #color then col = subMat.color
                        else if isProperty subMat #wireColor then col = subMat.wireColor
                    ) catch()
                    if col != undefined and (isKindOf col Color or isKindOf col Point3) do (
                        colStr = ((col.r as integer) as string) + "," + ((col.g as integer) as string) + "," + ((col.b as integer) as string)
                    )
                )
                fp += (sID as string) + ":" + (sName as string) + ":" + (subName as string) + ":" + subAnimHandle + ":" + (sEnabled as string) + ":" + colStr + ";"
            )
            return fp
        ) catch (
            return ""
        )
    )

    fn _jsh_MME_GetMultiMatData mat = (
        if mat == undefined or not (isKindOf mat Multimaterial or isKindOf mat multiSubMaterial) do return undefined
        
        -- Read-only check: determine effective slot count ignoring trailing undefined slots with duplicate IDs
        local count = mat.numsubs
        while count > 1 and (count > mat.materialList.count or mat.materialList[count] == undefined or not isValidObj mat.materialList[count]) do (
            local isGhost = false
            local curID = if count <= mat.materialIDList.count then mat.materialIDList[count] else count
            for prev = 1 to (count - 1) do (
                local prevID = if prev <= mat.materialIDList.count then mat.materialIDList[prev] else prev
                if curID == prevID do (
                    isGhost = true
                    exit
                )
            )
            if isGhost then (
                count -= 1
            ) else (
                exit
            )
        )

        local result = #()
        for i = 1 to count do (
            local subMat = undefined
            if i <= mat.materialList.count do (
                try ( subMat = mat.materialList[i] ) catch()
            )
            local hasSub = (subMat != undefined and isValidObj subMat)
            local subName = if hasSub then (subMat.name as string) else "None"
            local subClass = if hasSub then (classOf subMat as string) else "None"
            local sName = ""
            if i <= mat.names.count and mat.names[i] != undefined do (
                sName = mat.names[i] as string
            )
            local sID = i
            if i <= mat.materialIDList.count and mat.materialIDList[i] != undefined do (
                sID = mat.materialIDList[i] as integer
            )
            local sEnabled = true
            if i <= mat.mapEnabled.count and mat.mapEnabled[i] != undefined do (
                sEnabled = mat.mapEnabled[i] as booleanClass
            )
            
            local col = undefined
            if hasSub do (
                try (
                    if isProperty subMat #diffuse then col = subMat.diffuse
                    else if isProperty subMat #diffuseColor then col = subMat.diffuseColor
                    else if isProperty subMat #base_color then col = subMat.base_color
                    else if isProperty subMat #baseColor then col = subMat.baseColor
                    else if isProperty subMat #color then col = subMat.color
                    else if isProperty subMat #wireColor then col = subMat.wireColor
                ) catch()
            )
            local r = -1
            local g = -1
            local b = -1
            if col != undefined and (isKindOf col Color or isKindOf col Point3) do (
                r = col.r as integer
                g = col.g as integer
                b = col.b as integer
            )
            
            append result #(sID as integer, sName as string, subMat, subName as string, subClass as string, sEnabled as booleanClass, #(r, g, b))
        )
        result
    )

    fn _jsh_MME_GetSubMaterialColor subMat = (
        if subMat == undefined or not isValidObj subMat do return undefined
        local col = undefined
        try (
            if isProperty subMat #diffuse then col = subMat.diffuse
            else if isProperty subMat #diffuseColor then col = subMat.diffuseColor
            else if isProperty subMat #base_color then col = subMat.base_color
            else if isProperty subMat #baseColor then col = subMat.baseColor
            else if isProperty subMat #color then col = subMat.color
            else if isProperty subMat #wireColor then col = subMat.wireColor
        ) catch()
        col
    )

    fn _jsh_MME_AreSubMaterialsIdentical m1 m2 = (
        if m1 == undefined or m2 == undefined do return false
        if m1 == m2 do return true
        try (
            if (getHandleByAnim m1) == (getHandleByAnim m2) do return true
        ) catch()
        if (classOf m1) != (classOf m2) do return false
        if (m1.name as string) != (m2.name as string) do return false
        
        local c1 = _jsh_MME_GetSubMaterialColor m1
        local c2 = _jsh_MME_GetSubMaterialColor m2
        if c1 != undefined and c2 != undefined do (
            if (c1.r as integer) != (c2.r as integer) or (c1.g as integer) != (c2.g as integer) or (c1.b as integer) != (c2.b as integer) do return false
        )
        return true
    )

    fn _jsh_MME_SetSubMaterialColor subMat r g b = (
        if subMat == undefined or not isValidObj subMat do return false
        local newCol = color r g b
        try (
            if isProperty subMat #diffuse then subMat.diffuse = newCol
            else if isProperty subMat #diffuseColor then subMat.diffuseColor = newCol
            else if isProperty subMat #base_color then subMat.base_color = newCol
            else if isProperty subMat #baseColor then subMat.baseColor = newCol
            else if isProperty subMat #color then subMat.color = newCol
            else if isProperty subMat #wireColor then subMat.wireColor = newCol
        ) catch()
        try ( notifyDependents subMat ) catch()
        try ( redrawViews() ) catch()
        true
    )

    fn _jsh_MME_ApplyMultiMatData mat count subMats names ids enableds = (
        if mat == undefined or not (isKindOf mat Multimaterial or isKindOf mat multiSubMaterial) or count < 1 do return false
        
        while mat.materialList.count > count do (
            deleteItem mat.materialList mat.materialList.count
        )
        while mat.names.count > count do (
            deleteItem mat.names mat.names.count
        )
        while mat.materialIDList.count > count do (
            deleteItem mat.materialIDList mat.materialIDList.count
        )
        while mat.mapEnabled.count > count do (
            deleteItem mat.mapEnabled mat.mapEnabled.count
        )
        
        mat.numsubs = count
        for i = 1 to count do (
            mat.materialList[i] = subMats[i]
            mat.names[i] = names[i]
            mat.materialIDList[i] = ids[i]
            mat.mapEnabled[i] = enableds[i]
        )
        try ( notifyDependents mat ) catch()
        try ( redrawViews() ) catch()
        true
    )

    fn _jsh_MME_SetSlotName mat slotIndex newName syncSubMat = (
        if mat == undefined or not (isKindOf mat Multimaterial or isKindOf mat multiSubMaterial) do return false
        if slotIndex < 1 or slotIndex > mat.numsubs do return false
        try (
            mat.names[slotIndex] = newName as string
            if syncSubMat do (
                local subMat = mat.materialList[slotIndex]
                if subMat != undefined and isValidObj subMat do (
                    subMat.name = newName as string
                    try ( notifyDependents subMat ) catch()
                )
            )
            try ( notifyDependents mat ) catch()
            try ( redrawViews() ) catch()
            return true
        ) catch (
            return false
        )
    )

    fn _jsh_MME_SetSlotID mat slotIndex newID = (
        if mat == undefined or not (isKindOf mat Multimaterial or isKindOf mat multiSubMaterial) do return false
        if slotIndex < 1 or slotIndex > mat.numsubs do return false
        try (
            mat.materialIDList[slotIndex] = newID as integer
            notifyDependents mat
            redrawViews()
            return true
        ) catch (
            return false
        )
    )

    fn _jsh_MME_SetSlotEnabled mat slotIndex isEnabled = (
        if mat == undefined or not (isKindOf mat Multimaterial or isKindOf mat multiSubMaterial) do return false
        if slotIndex < 1 or slotIndex > mat.numsubs do return false
        try (
            mat.mapEnabled[slotIndex] = isEnabled as booleanClass
            notifyDependents mat
            redrawViews()
            return true
        ) catch (
            return false
        )
    )

    fn _jsh_MME_ClearSubObjectSelection obj = (
        if obj == undefined or not isValidNode obj do return ()
        try ( setCommandPanelTaskMode #create ) catch()
        try (
            if isKindOf obj Editable_Poly or (isProperty obj #baseObject and isKindOf obj.baseObject Editable_Poly) do (
                polyop.setFaceSelection obj #{}
                polyop.setEdgeSelection obj #{}
                polyop.setVertSelection obj #{}
            )
        ) catch()
        try (
            if isKindOf obj Editable_Mesh or (isProperty obj #baseObject and isKindOf obj.baseObject Editable_Mesh) or isKindOf obj TriMeshGeometry do (
                setFaceSelection obj #{}
                try ( setFaceSelection obj.baseObject #{} ) catch()
                setEdgeSelection obj #{}
                try ( setEdgeSelection obj.baseObject #{} ) catch()
                setVertSelection obj #{}
                try ( setVertSelection obj.baseObject #{} ) catch()
            )
        ) catch()
        try (
            if isProperty obj #modifiers do (
                for m in obj.modifiers do (
                    if isKindOf m Edit_Poly do (
                        try ( m.SetSelection #Face #{} ) catch()
                        try ( m.SetSelection #Vertex #{} ) catch()
                        try ( m.SetSelection #Edge #{} ) catch()
                    )
                    if isKindOf m Edit_Mesh do (
                        try ( setFaceSelection obj m #{} ) catch()
                        try ( setEdgeSelection obj m #{} ) catch()
                        try ( setVertSelection obj m #{} ) catch()
                    )
                )
            )
        ) catch()
    )

    fn _jsh_MME_UpdateEditPolyFaceIDs obj epMod oldIDs newIDs = (
        if obj == undefined or not isValidNode obj or epMod == undefined do return 0
        local count = 0
        local maxHwnd = windows.getMAXHWND()
        local origMode = getCommandPanelTaskMode()
        local prevSel = selection as array
        
        -- Lock Windows repainting ONLY while manipulating Edit_Poly modifier UI
        try ( windows.sendMessage maxHwnd 0x000B 0 0 ) catch()
        
        try (
            if (getCommandPanelTaskMode() != #modify) do setCommandPanelTaskMode #modify
            if selection.count != 1 or selection[1] != obj do select obj
            if modPanel.getCurrentObject() != epMod do modPanel.setCurrentObject epMod
            subObjectLevel = 4
            
            -- Ensure any existing sub-object selections are cleared
            try ( epMod.SetSelection #Face #{} ) catch()
            try ( epMod.SetSelection #Vertex #{} ) catch()
            try ( epMod.SetSelection #Edge #{} ) catch()
            
            -- Step 1: Pre-collect static face bitarrays for all changing oldIDs BEFORE any modifications
            local pending = #()
            for i = 1 to oldIDs.count do (
                local oID = oldIDs[i]
                local nID = newIDs[i]
                if oID != nID do (
                    local ba = #{}
                    try (
                        ba = polyop.getFacesByMatID obj oID
                    ) catch()
                    if ba.isEmpty do (
                        try (
                            epMod.selectByMaterialID = (oID - 1)
                            epMod.ButtonOp #SelectByMaterial
                            ba = epMod.GetSelection #Face
                        ) catch()
                    )
                    if not ba.isEmpty do (
                        append pending #(nID, ba)
                    )
                )
            )
            
            -- Step 2: Apply the target newIDs directly to the pre-collected bitarrays using SetOperation & Commit
            for change in pending do (
                local nID = change[1]
                local ba = change[2]
                
                epMod.SetSelection #Face #{}
                epMod.Select #Face ba
                epMod.materialIDToSet = (nID - 1)
                epMod.SetOperation #SetMaterial
                epMod.Commit()
                count += ba.numberSet
            )
            
            epMod.SetSelection #Face #{}
            subObjectLevel = 0
            
        ) catch (
            format "Error updating Edit_Poly Face IDs: %\n" (getCurrentException())
        )
        
        -- Restore original command panel mode and selection
        try (
            if origMode != undefined and (getCommandPanelTaskMode() != origMode) do (
                setCommandPanelTaskMode origMode
            )
        ) catch()
        
        try (
            if prevSel.count > 0 then select prevSel else clearSelection()
        ) catch()
        
        -- Unlock Windows repainting
        try ( windows.sendMessage maxHwnd 0x000B 1 0 ) catch()
        try ( completeRedraw() ) catch()
        
        count
    )

    fn _jsh_MME_UpdateFaceIDs obj oldIDs newIDs = (
        if obj == undefined or not isValidNode obj do return 0
        local count = 0
        
        -- Clear any active sub-object polygon/element/vertex selections
        _jsh_MME_ClearSubObjectSelection obj
        
        local hasModifiers = (isProperty obj #modifiers and obj.modifiers.count > 0)
        
        if hasModifiers then (
            local topMod = obj.modifiers[1]
            local ep = if isKindOf topMod Edit_Poly then topMod else undefined
            if ep == undefined do (
                ep = Edit_Poly()
                addModifier obj ep
            )
            count = _jsh_MME_UpdateEditPolyFaceIDs obj ep oldIDs newIDs
        ) else (
            -- Fast, direct in-memory method for collapsed Editable_Poly / Editable_Mesh
            local target = if (isProperty obj #baseObject and isValidObj obj.baseObject) then obj.baseObject else obj
            local isPoly = (isKindOf target Editable_Poly or isKindOf obj Editable_Poly)
            local isMesh = (isKindOf target Editable_Mesh or isKindOf obj Editable_Mesh or isKindOf target TriMeshGeometry or isKindOf obj TriMeshGeometry)
            
            if isPoly then (
                local polyObj = if isKindOf target Editable_Poly then target else obj
                with redraw off (
                    local pending = #()
                    for i = 1 to oldIDs.count do (
                        local oID = oldIDs[i]
                        local nID = newIDs[i]
                        if oID != nID do (
                            local ba = polyop.getFacesByMatID polyObj oID
                            if not ba.isEmpty do append pending #(nID, ba)
                        )
                    )
                    for change in pending do (
                        local nID = change[1]
                        local ba = change[2]
                        polyop.setFaceMatID polyObj ba nID
                        count += ba.numberSet
                    )
                    try ( update polyObj ) catch()
                    try ( update obj ) catch()
                )
            ) else if isMesh then (
                with redraw off (
                    local numF = getNumFaces obj
                    local pending = #()
                    for i = 1 to oldIDs.count do (
                        local oID = oldIDs[i]
                        local nID = newIDs[i]
                        if oID != nID do (
                            local ba = #{}
                            for f = 1 to numF do (
                                if (getFaceMatID obj f) == oID do ba[f] = true
                            )
                            if not ba.isEmpty do append pending #(nID, ba)
                        )
                    )
                    for change in pending do (
                        local nID = change[1]
                        local ba = change[2]
                        for f in ba do (
                            setFaceMatID obj f nID
                        )
                        count += ba.numberSet
                    )
                    try ( update obj ) catch()
                )
            ) else (
                local ep = Edit_Poly()
                addModifier obj ep
                count = _jsh_MME_UpdateEditPolyFaceIDs obj ep oldIDs newIDs
            )
            try ( redrawViews() ) catch()
        )
        
        count
    )

    fn _jsh_MME_GetFaceIDCounts obj = (
        local result = #()
        if obj == undefined or not isValidNode obj do return result
        
        local target = if (isProperty obj #baseObject and isValidObj obj.baseObject) then obj.baseObject else obj
        
        if isKindOf target Editable_Poly or isKindOf obj Editable_Poly then (
            local polyObj = if isKindOf target Editable_Poly then target else obj
            for matID = 1 to 256 do (
                local ba = polyop.getFacesByMatID polyObj matID
                if not ba.isEmpty do (
                    append result #(matID, ba.numberSet)
                )
            )
        ) else if isKindOf target Editable_Mesh or isKindOf obj Editable_Mesh or isKindOf target TriMeshGeometry or isKindOf obj TriMeshGeometry then (
            local numF = getNumFaces obj
            local counts = #()
            for f = 1 to numF do (
                local id = getFaceMatID obj f
                if id != undefined and id > 0 do (
                    while counts.count < id do append counts 0
                    counts[id] += 1
                )
            )
            for matID = 1 to counts.count do (
                if counts[matID] != undefined and counts[matID] > 0 do (
                    append result #(matID, counts[matID])
                )
            )
        ) else (
            try (
                local numF = polyop.getNumFaces obj
                for matID = 1 to 256 do (
                    local ba = polyop.getFacesByMatID obj matID
                    if not ba.isEmpty do (
                        append result #(matID, ba.numberSet)
                    )
                )
            ) catch (
                try (
                    local tempMesh = snapshotAsMesh obj
                    if tempMesh != undefined do (
                        for matID = 1 to 256 do (
                            local ba = meshop.getFacesByMatID tempMesh matID
                            if not ba.isEmpty do (
                                append result #(matID, ba.numberSet)
                            )
                        )
                        delete tempMesh
                    )
                ) catch()
            )
        )
        result
    )
    """
    try:
        rt.execute(mxs_code)
    except Exception as e:
        print("Error registering MaxScript helper functions: {}".format(e))

init_maxscript_helpers()


def create_color_swatch_pixmap(qcolor, size=18):
    """Creates a rounded square pixmap for previewing material color."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    if qcolor is None:
        painter.setBrush(QBrush(QColor(60, 60, 60)))
        painter.setPen(QPen(QColor(90, 90, 90), 1))
        painter.drawRoundedRect(1, 1, size - 2, size - 2, 3, 3)
        painter.setPen(QPen(QColor(160, 70, 70), 1.5))
        painter.drawLine(3, 3, size - 4, size - 4)
    else:
        painter.setBrush(QBrush(qcolor))
        painter.setPen(QPen(QColor(30, 30, 30), 1))
        painter.drawRoundedRect(1, 1, size - 2, size - 2, 3, 3)

    painter.end()
    return pixmap


class CustomHeaderView(QHeaderView):
    def __init__(self, orientation, parent=None):
        super(CustomHeaderView, self).__init__(orientation, parent)
        self.setSectionsClickable(True)
        self.setHighlightSections(True)
        self.setMouseTracking(True)

    def mouseMoveEvent(self, event):
        idx = self.logicalIndexAt(event.pos())
        if idx == 0:
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
        super(CustomHeaderView, self).mouseMoveEvent(event)

    def leaveEvent(self, event):
        self.setCursor(Qt.ArrowCursor)
        super(CustomHeaderView, self).leaveEvent(event)

    def paintSection(self, painter, rect, logicalIndex):
        super(CustomHeaderView, self).paintSection(painter, rect, logicalIndex)
        if logicalIndex == 0:
            main_ui = self.window()
            duplicate_ids = getattr(main_ui, '_duplicate_ids', set())
            if duplicate_ids:
                painter.save()
                painter.setRenderHint(QPainter.Antialiasing)
                box_rect = QRect(rect.x() + 3, rect.y() + 3, rect.width() - 6, rect.height() - 6)
                painter.setBrush(QBrush(QColor(180, 45, 45, 90)))
                painter.setPen(QPen(QColor(235, 75, 75), 1.5))
                painter.drawRoundedRect(box_rect, 3, 3)
                painter.restore()


class CellEditorEnterFilter(QtCore.QObject):
    def __init__(self, table, row, col, parent=None):
        super(CellEditorEnterFilter, self).__init__(parent)
        self.table = table
        self.row = row
        self.col = col

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            editor = obj
            self.table.commitData(editor)
            self.table.closeEditor(editor, QtWidgets.QAbstractItemDelegate.NoHint)
            next_row = self.row + 1
            if next_row < self.table.rowCount():
                def move_and_select():
                    self.table.setCurrentCell(next_row, self.col)
                    self.table.selectRow(next_row)
                    target_idx = self.table.model().index(next_row, self.col)
                    self.table.setCurrentIndex(target_idx)
                QTimer.singleShot(10, move_and_select)
            return True
        return super(CellEditorEnterFilter, self).eventFilter(obj, event)


class UnifiedTableItemDelegate(QStyledItemDelegate):
    def __init__(self, parent_table):
        super(UnifiedTableItemDelegate, self).__init__(parent_table)
        self.table = parent_table

    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        row = index.row()
        col = index.column()
        rect = option.rect

        main_ui = self.table.window()
        if not hasattr(main_ui, 'slots_data') or row >= len(main_ui.slots_data):
            painter.restore()
            return
        slot = main_ui.slots_data[row]

        preview_groups = getattr(main_ui, '_preview_duplicate_groups', None)
        in_dup_preview = bool(preview_groups and (row in preview_groups))

        if option.state & QtWidgets.QStyle.State_Selected:
            painter.fillRect(rect, QColor(30, 73, 118))
        elif in_dup_preview:
            bg = QColor(95, 60, 24) if (row % 2 == 1) else QColor(80, 48, 18)
            painter.fillRect(rect, bg)
        else:
            bg = QColor(82, 82, 82) if (row % 2 == 1) else QColor(72, 72, 72)
            painter.fillRect(rect, bg)

        if col == 0:
            painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
            slot_id = slot.get('id')
            duplicate_ids = getattr(main_ui, '_duplicate_ids', set())

            if slot_id in duplicate_ids:
                box_rect = QRect(rect.x() + 4, rect.y() + 3, rect.width() - 8, rect.height() - 6)
                painter.setBrush(QBrush(QColor(180, 45, 45, 120)))
                painter.setPen(QPen(QColor(235, 75, 75), 1.5))
                painter.drawRoundedRect(box_rect, 3, 3)
                painter.setPen(QPen(QColor(255, 220, 220)))
            else:
                painter.setPen(QPen(QColor(235, 235, 235)))

            painter.drawText(rect, Qt.AlignCenter, str(slot_id))

        elif col == 1:
            swatch_pix = create_color_swatch_pixmap(slot.get('color'), size=18)
            pix_x = rect.x() + (rect.width() - swatch_pix.width()) // 2
            pix_y = rect.y() + (rect.height() - swatch_pix.height()) // 2
            painter.drawPixmap(pix_x, pix_y, swatch_pix)

        elif col == 2:
            painter.setFont(QFont("Segoe UI", 9))
            painter.setPen(QPen(QColor(235, 235, 235)))
            text_rect = QRect(rect.x() + 9, rect.y(), rect.width() - 18, rect.height())
            elided_name = painter.fontMetrics().elidedText(slot.get('name', ''), Qt.ElideRight, text_rect.width())
            painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, elided_name)

        elif col == 3:
            painter.setFont(QFont("Segoe UI", 9))
            is_hovered = (hasattr(self.table, '_hover_row') and hasattr(self.table, '_hover_col') and
                          self.table._hover_row == row and self.table._hover_col == 3 and not self.table._is_dragging)

            if slot.get('sub_mat'):
                sub_text = slot.get('sub_mat_name', 'None')
                if slot.get('sub_mat_class') and slot['sub_mat_class'] != 'None':
                    sub_text += "  ({})".format(slot['sub_mat_class'])

                box_rect = QRect(rect.x() + 3, rect.y() + 2, rect.width() - 6, rect.height() - 4)

                if is_hovered:
                    painter.setPen(QPen(QColor(98, 98, 98), 1))
                    painter.setBrush(QBrush(QColor(78, 78, 78)))
                    painter.drawRoundedRect(box_rect, 4, 4)
                    painter.setPen(QPen(QColor(255, 255, 255)))
                else:
                    painter.setPen(QPen(QColor(225, 225, 225)))

                text_rect = QRect(box_rect.x() + 6, box_rect.y(), box_rect.width() - 12, box_rect.height())
                elided_sub = painter.fontMetrics().elidedText(sub_text, Qt.ElideRight, text_rect.width())
                painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, elided_sub)
            else:
                painter.setPen(QPen(QColor(135, 135, 135)))
                painter.drawText(rect, Qt.AlignCenter, "None")

        elif col == 4:
            chk_size = 14
            chk_x = rect.x() + (rect.width() - chk_size) // 2
            chk_y = rect.y() + (rect.height() - chk_size) // 2
            is_on = slot.get('enabled', True)
            if is_on:
                painter.setBrush(QBrush(QColor(30, 155, 253)))
                painter.setPen(QPen(QColor(30, 155, 253), 1))
                painter.drawRoundedRect(chk_x, chk_y, chk_size, chk_size, 3, 3)
                painter.setPen(QPen(QColor(255, 255, 255), 1.6))
                painter.drawLine(chk_x + 3, chk_y + 7, chk_x + 6, chk_y + 10)
                painter.drawLine(chk_x + 6, chk_y + 10, chk_x + 11, chk_y + 4)
            else:
                painter.setBrush(QBrush(QColor(56, 56, 56)))
                painter.setPen(QPen(QColor(100, 100, 100), 1))
                painter.drawRoundedRect(chk_x, chk_y, chk_size, chk_size, 3, 3)

        elif col == 5:
            used_faces = slot.get('face_count', 0)
            used_text = str(used_faces) if used_faces > 0 else "-"
            painter.setFont(QFont("Segoe UI", 9))
            if used_faces > 0:
                painter.setPen(QPen(QColor(30, 155, 253)))
            else:
                painter.setPen(QPen(QColor(130, 130, 130)))
            painter.drawText(rect, Qt.AlignCenter, used_text)

        if in_dup_preview:
            grp_id = preview_groups[row]
            painter.setPen(QPen(QColor(230, 126, 34), 1.5))
            if col == 0:
                painter.drawLine(rect.left(), rect.top(), rect.left(), rect.bottom())
            if col == 5:
                painter.drawLine(rect.right(), rect.top(), rect.right(), rect.bottom())
            if row == 0 or preview_groups.get(row - 1) != grp_id:
                painter.drawLine(rect.left(), rect.top(), rect.right(), rect.top())
            if row == len(main_ui.slots_data) - 1 or preview_groups.get(row + 1) != grp_id:
                painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())

        painter.restore()

    def createEditor(self, parent, option, index):
        if index.column() in (0, 2):
            editor = super(UnifiedTableItemDelegate, self).createEditor(parent, option, index)
            if isinstance(editor, QLineEdit):
                editor.setStyleSheet("""
                    QLineEdit {
                        background-color: #2b2b2b;
                        color: #ffffff;
                        border: 1px solid #1e9bfd;
                        border-radius: 2px;
                        padding: 2px 4px;
                    }
                """)
                filter_obj = CellEditorEnterFilter(self.table, index.row(), index.column(), editor)
                editor.installEventFilter(filter_obj)
            return editor
        return None

    def setModelData(self, editor, model, index):
        main_ui = self.table.window()
        row = index.row()
        col = index.column()

        if col == 2 and isinstance(editor, QLineEdit):
            new_name = editor.text().strip()
            if hasattr(main_ui, 'slots_data') and row < len(main_ui.slots_data):
                slot = main_ui.slots_data[row]
                slot['name'] = new_name

                # Check if Sync Names is active and sub-material exists
                sync_sub = bool(hasattr(main_ui, 'chk_sync_names') and main_ui.chk_sync_names.isChecked() and slot.get('sub_mat') is not None)

                if sync_sub and new_name:
                    slot['sub_mat_name'] = new_name
                    sub_text = new_name
                    if slot.get('sub_mat_class') and slot['sub_mat_class'] != 'None':
                        sub_text += "  ({})".format(slot['sub_mat_class'])
                    sub_item = self.table.item(row, 3)
                    if sub_item:
                        sub_item.setText(sub_text)

                if hasattr(main_ui, 'is_live_sync') and main_ui.is_live_sync and main_ui.target_material and rt:
                    try:
                        rt._jsh_MME_SetSlotName(main_ui.target_material, row + 1, new_name, sync_sub)
                        if sync_sub and new_name:
                            main_ui.set_status("● Live Sync: Sub-material renamed to '{}'".format(new_name))
                        else:
                            main_ui.set_status("● Live Sync: Slot renamed to '{}'".format(new_name))
                        try:
                            main_ui._last_fingerprint = str(rt._jsh_MME_GetMatFingerprint(main_ui.target_material))
                        except Exception:
                            pass
                    except Exception as e:
                        print("Error setting slot name: {}".format(e))
                elif not (hasattr(main_ui, 'is_live_sync') and main_ui.is_live_sync):
                    main_ui.set_status("● Paused: Slot renamed")

                self.table.viewport().update()

        super(UnifiedTableItemDelegate, self).setModelData(editor, model, index)

    def editorEvent(self, event, model, option, index):
        if index.column() == 4:
            if event.type() == QtCore.QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                main_ui = self.table.window()
                row = index.row()
                if hasattr(main_ui, 'slots_data') and row < len(main_ui.slots_data):
                    slot = main_ui.slots_data[row]
                    slot['enabled'] = not slot.get('enabled', True)
                    self.table.viewport().update()
                    if hasattr(main_ui, 'is_live_sync') and main_ui.is_live_sync:
                        if main_ui.target_material and rt:
                            try:
                                rt._jsh_MME_SetSlotEnabled(main_ui.target_material, row + 1, slot['enabled'])
                                main_ui.set_status("● Live Sync: Slot #{} {}".format(slot['id'], "Enabled" if slot['enabled'] else "Disabled"))
                                try:
                                    main_ui._last_fingerprint = str(rt._jsh_MME_GetMatFingerprint(main_ui.target_material))
                                except Exception:
                                    pass
                            except Exception:
                                main_ui.sync_to_max("Toggle Slot Enable")
                        else:
                            main_ui.sync_to_max("Toggle Slot Enable")
                    else:
                        main_ui.set_status("● Paused: Slot #{} toggled".format(slot['id']))
                    return True
        return super(UnifiedTableItemDelegate, self).editorEvent(event, model, option, index)


class ReorderableTableWidget(QTableWidget):
    rows_reordered = Signal()

    def __init__(self, parent=None):
        super(ReorderableTableWidget, self).__init__(parent)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setShowGrid(False)
        self.verticalHeader().setVisible(False)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.setFont(QFont("Segoe UI", 9))

        self.setDragEnabled(False)
        self.setAcceptDrops(False)

        self._is_dragging = False
        self._drag_row_index = -1
        self._drag_start_pos = QPoint()
        self._current_mouse_y = 0
        self._row_height = 31
        self._hover_row = -1
        self._hover_col = -1

        self._active_anim = {}
        self._row_anim_offsets = {}
        self._anim_duration = 0.18

        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(16)
        self._anim_timer.timeout.connect(self._on_anim_step)

        self._scroll_timer = QTimer(self)
        self._scroll_timer.setInterval(140)
        self._scroll_timer.timeout.connect(self._handle_auto_scroll)
        self._scroll_direction = 0

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            curr_index = self.currentIndex()
            if curr_index.isValid() and self.state() != QAbstractItemView.EditingState:
                col = curr_index.column()
                target_col = col if col in (0, 2) else 2
                target_index = self.model().index(curr_index.row(), target_col)
                self.setCurrentIndex(target_index)
                self.edit(target_index)
                event.accept()
                return
        elif event.key() == Qt.Key_Delete:
            main_ui = self.window()
            if hasattr(main_ui, 'remove_selected_slot'):
                main_ui.remove_selected_slot()
                event.accept()
                return
        super(ReorderableTableWidget, self).keyPressEvent(event)

    def leaveEvent(self, event):
        if self._hover_row != -1 or self._hover_col != -1:
            self._hover_row = -1
            self._hover_col = -1
            self.viewport().update()
        self.viewport().setCursor(Qt.ArrowCursor)
        super(ReorderableTableWidget, self).leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            item = self.itemAt(event.pos())
            if item:
                self._drag_row_index = item.row()
                self._drag_start_pos = event.pos()
                self._is_dragging = False
            else:
                self._drag_row_index = -1
        super(ReorderableTableWidget, self).mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (event.buttons() & Qt.LeftButton) and self._drag_row_index >= 0:
            pos = event.pos()

            if not self._is_dragging:
                if (pos - self._drag_start_pos).manhattanLength() > 5:
                    self._is_dragging = True
                    self._scroll_timer.start()
                    self.viewport().setCursor(Qt.ClosedHandCursor)

            if self._is_dragging:
                self._current_mouse_y = max(0, min(pos.y(), self.viewport().height()))

                scroll_margin = 28
                if pos.y() < scroll_margin:
                    self._scroll_direction = -1
                elif pos.y() > self.viewport().height() - scroll_margin:
                    self._scroll_direction = 1
                else:
                    self._scroll_direction = 0

                self._update_target_row_from_mouse()
                return

        # Track hover cell and update cursor when not dragging
        pos = event.pos()
        item = self.itemAt(pos)
        if item:
            hover_row = item.row()
            hover_col = item.column()
        else:
            hover_row = -1
            hover_col = -1

        if hover_row != self._hover_row or hover_col != self._hover_col:
            self._hover_row = hover_row
            self._hover_col = hover_col
            self.viewport().update()

        if hover_row >= 0:
            main_ui = self.window()
            slots_data = getattr(main_ui, 'slots_data', [])
            has_submat = False
            if hover_row < len(slots_data):
                has_submat = (slots_data[hover_row].get('sub_mat') is not None)

            if hover_col == 1 or (hover_col == 3 and has_submat) or hover_col == 4:
                self.viewport().setCursor(Qt.PointingHandCursor)
            else:
                self.viewport().setCursor(Qt.ArrowCursor)
        else:
            self.viewport().setCursor(Qt.ArrowCursor)

        super(ReorderableTableWidget, self).mouseMoveEvent(event)

    def _update_target_row_from_mouse(self):
        if not self._is_dragging:
            return

        target_item = self.itemAt(QPoint(self.viewport().width() // 2, self._current_mouse_y))
        if target_item:
            target_row = target_item.row()
        else:
            if self._current_mouse_y <= 20:
                target_row = 0
            else:
                target_row = self.rowCount() - 1

        if 0 <= target_row < self.rowCount() and target_row != self._drag_row_index:
            self._displace_and_move_row(self._drag_row_index, target_row)
            self._drag_row_index = target_row

        self.viewport().update()

    def mouseReleaseEvent(self, event):
        if self._is_dragging:
            final_target_row = self._drag_row_index
            self._is_dragging = False
            self._scroll_timer.stop()
            self._anim_timer.stop()
            self._scroll_direction = 0
            self._active_anim.clear()
            self._row_anim_offsets.clear()
            self.viewport().setCursor(Qt.ArrowCursor)

            main_ui = self.window()
            if hasattr(main_ui, 'finish_drag_reorder'):
                main_ui.finish_drag_reorder(final_target_row)
            else:
                self.selectRow(final_target_row)

            self.rows_reordered.emit()
            self.viewport().update()
            self._drag_row_index = -1
            event.accept()
            return

        self._drag_row_index = -1
        super(ReorderableTableWidget, self).mouseReleaseEvent(event)

    def _handle_auto_scroll(self):
        if not self._is_dragging or self._scroll_direction == 0:
            return
        sb = self.verticalScrollBar()
        new_val = sb.value() + self._scroll_direction
        if 0 <= new_val <= sb.maximum():
            sb.setValue(new_val)
            self._update_target_row_from_mouse()

    def _displace_and_move_row(self, source_row, target_row):
        main_ui = self.window()
        if not hasattr(main_ui, 'slots_data'):
            return

        now = time.time()
        h = self._row_height

        if source_row < target_row:
            for r in range(source_row, target_row):
                curr = self._row_anim_offsets.get(r, 0.0)
                self._active_anim[r] = {
                    'start_offset': curr + h,
                    'start_time': now,
                    'duration': self._anim_duration
                }
        else:
            for r in range(target_row + 1, source_row + 1):
                curr = self._row_anim_offsets.get(r, 0.0)
                self._active_anim[r] = {
                    'start_offset': curr - h,
                    'start_time': now,
                    'duration': self._anim_duration
                }

        main_ui.move_row_data_live(source_row, target_row, refresh_ui=True)

        if not self._anim_timer.isActive():
            self._anim_timer.start()

    def _on_anim_step(self):
        now = time.time()
        still_running = False

        for r, data in list(self._active_anim.items()):
            elapsed = now - data['start_time']
            t = min(1.0, elapsed / data['duration'])
            ease = 1.0 - math.pow(1.0 - t, 3)
            offset = data['start_offset'] * (1.0 - ease)
            self._row_anim_offsets[r] = offset

            if t < 1.0:
                still_running = True
            else:
                del self._active_anim[r]
                self._row_anim_offsets[r] = 0.0

        if not still_running:
            self._anim_timer.stop()

        self.viewport().update()

    def _paint_row_content(self, painter, slot, y_draw, is_ghost=False):
        h = self._row_height
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        # ID
        x0 = self.columnViewportPosition(0)
        w0 = self.columnWidth(0)
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        slot_id = slot.get('id')
        main_ui = self.window()
        duplicate_ids = getattr(main_ui, '_duplicate_ids', set())
        if slot_id in duplicate_ids:
            box_rect = QRect(x0 + 4, int(y_draw) + 3, w0 - 8, h - 6)
            painter.setBrush(QBrush(QColor(180, 45, 45, 120)))
            painter.setPen(QPen(QColor(235, 75, 75), 1.5))
            painter.drawRoundedRect(box_rect, 3, 3)
            painter.setPen(QPen(QColor(255, 220, 220)))
        else:
            painter.setPen(QPen(QColor(235, 235, 235)))
        painter.drawText(QRect(x0, int(y_draw), w0, h), Qt.AlignCenter, str(slot_id))

        # Color Swatch
        x1 = self.columnViewportPosition(1)
        w1 = self.columnWidth(1)
        swatch_pix = create_color_swatch_pixmap(slot.get('color'), size=18)
        pix_x = x1 + (w1 - swatch_pix.width()) // 2
        pix_y = int(y_draw) + (h - swatch_pix.height()) // 2
        painter.drawPixmap(pix_x, pix_y, swatch_pix)

        # Name
        x2 = self.columnViewportPosition(2)
        w2 = self.columnWidth(2)
        painter.setFont(QFont("Segoe UI", 9))
        painter.setPen(QPen(QColor(235, 235, 235)))
        text_rect = QRect(x2 + 9, int(y_draw), w2 - 18, h)
        elided_name = painter.fontMetrics().elidedText(slot.get('name', ''), Qt.ElideRight, text_rect.width())
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, elided_name)

        # Sub-Material
        x3 = self.columnViewportPosition(3)
        w3 = self.columnWidth(3)
        if slot.get('sub_mat'):
            sub_text = slot.get('sub_mat_name', 'None')
            if slot.get('sub_mat_class') and slot['sub_mat_class'] != 'None':
                sub_text += "  ({})".format(slot['sub_mat_class'])
            painter.setPen(QPen(QColor(225, 225, 225)))
            sub_rect = QRect(x3 + 9, int(y_draw), w3 - 18, h)
            elided_sub = painter.fontMetrics().elidedText(sub_text, Qt.ElideRight, sub_rect.width())
            painter.drawText(sub_rect, Qt.AlignVCenter | Qt.AlignLeft, elided_sub)
        else:
            painter.setPen(QPen(QColor(135, 135, 135)))
            rect3 = QRect(x3, int(y_draw), w3, h)
            painter.drawText(rect3, Qt.AlignCenter, "None")

        # Enabled Checkbox
        x4 = self.columnViewportPosition(4)
        w4 = self.columnWidth(4)
        chk_size = 14
        chk_x = x4 + (w4 - chk_size) // 2
        chk_y = int(y_draw) + (h - chk_size) // 2
        is_on = slot.get('enabled', True)
        if is_on:
            painter.setBrush(QBrush(QColor(30, 155, 253)))
            painter.setPen(QPen(QColor(30, 155, 253), 1))
            painter.drawRoundedRect(chk_x, chk_y, chk_size, chk_size, 3, 3)
            painter.setPen(QPen(QColor(255, 255, 255), 1.6))
            painter.drawLine(chk_x + 3, chk_y + 7, chk_x + 6, chk_y + 10)
            painter.drawLine(chk_x + 6, chk_y + 10, chk_x + 11, chk_y + 4)
        else:
            painter.setBrush(QBrush(QColor(56, 56, 56)))
            painter.setPen(QPen(QColor(100, 100, 100), 1))
            painter.drawRoundedRect(chk_x, chk_y, chk_size, chk_size, 3, 3)

        # Usage Count
        x5 = self.columnViewportPosition(5)
        w5 = self.columnWidth(5)
        used_faces = slot.get('face_count', 0)
        used_text = str(used_faces) if used_faces > 0 else "-"
        painter.setFont(QFont("Segoe UI", 9))
        if used_faces > 0:
            painter.setPen(QPen(QColor(30, 155, 253)))
        else:
            painter.setPen(QPen(QColor(130, 130, 130)))
        painter.drawText(QRect(x5, int(y_draw), w5, h), Qt.AlignCenter, used_text)

    def paintEvent(self, event):
        if self._is_dragging:
            main_ui = self.window()
            if not hasattr(main_ui, 'slots_data'):
                super(ReorderableTableWidget, self).paintEvent(event)
                return

            painter = QPainter(self.viewport())
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.TextAntialiasing)

            painter.fillRect(self.viewport().rect(), QColor(72, 72, 72))

            h = self._row_height
            w = self.viewport().width()
            num_rows = len(main_ui.slots_data)

            for r in range(num_rows):
                y_base = self.rowViewportPosition(r)
                if y_base + h < 0 or y_base > self.viewport().height():
                    continue

                if r == self._drag_row_index:
                    painter.setPen(QPen(QColor(100, 100, 100), 1, Qt.DashLine))
                    painter.setBrush(QBrush(QColor(50, 50, 50)))
                    painter.drawRoundedRect(3, y_base + 1, w - 6, h - 2, 4, 4)
                else:
                    offset = self._row_anim_offsets.get(r, 0.0)
                    y_draw = y_base + offset

                    bg_color = QColor(82, 82, 82) if (r % 2 == 1) else QColor(72, 72, 72)
                    painter.fillRect(QRect(0, int(y_draw), w, h), bg_color)

                    slot = main_ui.slots_data[r]
                    self._paint_row_content(painter, slot, y_draw, is_ghost=False)

            if 0 <= self._drag_row_index < num_rows:
                y_ghost = self._current_mouse_y - (h // 2)
                y_ghost = max(2, min(y_ghost, self.viewport().height() - h - 2))

                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(QColor(0, 0, 0, 140)))
                painter.drawRoundedRect(4, y_ghost + 4, w - 8, h, 4, 4)

                painter.setBrush(QBrush(QColor(30, 73, 118, 240)))
                painter.drawRoundedRect(2, y_ghost, w - 4, h, 4, 4)

                dragged_slot = main_ui.slots_data[self._drag_row_index]
                self._paint_row_content(painter, dragged_slot, y_ghost, is_ghost=True)

                glow_pen = QPen(QColor(30, 155, 253, 245), 2)
                painter.setPen(glow_pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawRoundedRect(2, y_ghost, w - 4, h, 4, 4)

            painter.end()
            return

        super(ReorderableTableWidget, self).paintEvent(event)

        if self.rowCount() == 0:
            painter = QPainter(self.viewport())
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.TextAntialiasing)

            painter.setFont(QFont("Segoe UI", 11, QFont.Bold))
            painter.setPen(QColor("#b5b5b5"))
            rect_title = QRect(0, self.viewport().height() // 2 - 24, self.viewport().width(), 24)
            painter.drawText(rect_title, Qt.AlignCenter, "No Multi/Sub-Object Material Selected")

            painter.setFont(QFont("Segoe UI", 9))
            painter.setPen(QColor("#787878"))
            rect_sub = QRect(0, self.viewport().height() // 2 + 4, self.viewport().width(), 20)
            painter.drawText(rect_sub, Qt.AlignCenter, "Select an object in viewport or a material node in SME")

            painter.end()


class WarningSuffixCheckBox(QCheckBox):
    """Checkbox supporting an auxiliary warning text suffix drawn in warning orange."""
    def __init__(self, text="", parent=None):
        super(WarningSuffixCheckBox, self).__init__(text, parent)
        self._warning_suffix = ""

    def set_warning_suffix(self, suffix):
        if self._warning_suffix != suffix:
            self._warning_suffix = suffix
            self.updateGeometry()
            self.update()

    def sizeHint(self):
        hint = super(WarningSuffixCheckBox, self).sizeHint()
        if self._warning_suffix:
            fm = self.fontMetrics()
            try:
                extra_w = fm.horizontalAdvance(" " + self._warning_suffix)
            except AttributeError:
                extra_w = fm.width(" " + self._warning_suffix)
            hint.setWidth(hint.width() + extra_w + 4)
        return hint

    def paintEvent(self, event):
        super(WarningSuffixCheckBox, self).paintEvent(event)
        if self._warning_suffix:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setFont(self.font())
            painter.setPen(QColor("#ff9d2e"))  # Vibrant warm warning orange

            fm = self.fontMetrics()
            try:
                base_w = fm.horizontalAdvance(self.text())
            except AttributeError:
                base_w = fm.width(self.text())

            opt = QtWidgets.QStyleOptionButton()
            self.initStyleOption(opt)
            indicator_rect = self.style().subElementRect(QtWidgets.QStyle.SE_CheckBoxIndicator, opt, self)
            spacing = 8
            x = indicator_rect.right() + spacing + base_w + 5
            draw_rect = QRect(x, 0, max(0, self.width() - x), self.height())
            painter.drawText(draw_rect, Qt.AlignVCenter | Qt.AlignLeft, self._warning_suffix)
            painter.end()


class MultiMaterialEditorUI(QDialog):
    def __init__(self, target_material=None, parent=None):
        max_parent = parent if parent is not None else get_max_main_window()
        super(MultiMaterialEditorUI, self).__init__(max_parent)

        init_maxscript_helpers()
        self.target_material = target_material
        self._current_mat_handle = 0
        self._last_fingerprint = ""
        self.is_live_sync = True
        self._current_status_text = "● Live Sync Active"
        self.slots_data = []
        self.initial_id_map = {}
        self._duplicate_ids = set()
        self._preview_duplicate_groups = None
        self._backup_slots_data = None
        self._current_scene_objs_using_mat = []
        self._last_sel_handles = []
        self.is_locked = False
        self.is_loading = False

        self.setWindowTitle("Multi-Material Editor | JSH")
        self.resize(750, 570)
        self.setMinimumSize(620, 420)
        self.setWindowFlags((self.windowFlags() | Qt.Window) & ~Qt.WindowContextHelpButtonHint)

        self.setup_style()
        self.init_ui()

        if self.target_material:
            self.load_material(self.target_material)
        else:
            self.check_selection_and_material_changes()

        self._sync_timer = QTimer(self)
        self._sync_timer.setInterval(200)
        self._sync_timer.timeout.connect(self.check_selection_and_material_changes)
        self._sync_timer.start()

    def save_checkbox_settings(self):
        if hasattr(self, 'chk_auto_renumber') and hasattr(self, 'chk_sync_names') and hasattr(self, 'chk_update_faces'):
            save_config_settings({
                'auto_renumber_ids': self.chk_auto_renumber.isChecked(),
                'sync_names': self.chk_sync_names.isChecked(),
                'update_ids_on_geometry': self.chk_update_faces.isChecked()
            })

    def closeEvent(self, event):
        self.save_checkbox_settings()
        if hasattr(self, '_sync_timer') and self._sync_timer.isActive():
            self._sync_timer.stop()
        super(MultiMaterialEditorUI, self).closeEvent(event)

    def setup_style(self):
        check_icon = get_cached_checkmark_icon_path()
        style = """
            QDialog {
                background-color: #444444;
                color: #dedede;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 12px;
            }
            QMessageBox {
                background-color: #444444;
            }
            QMessageBox QLabel {
                font-size: 13px;
                color: #f0f0f0;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QMessageBox QPushButton {
                min-width: 78px;
                font-size: 12px;
                padding: 6px 14px;
            }
            QFrame#headerFrame {
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 2px 4px;
            }
            QFrame#headerFrame:hover {
                background-color: #4e4e4e;
                border: 1px solid #626262;
            }
            QLabel {
                color: #dedede;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLabel#matTitle {
                font-size: 14px;
                font-weight: bold;
                color: #ffffff;
            }
            QLabel#slotCountLabel {
                font-size: 14px;
                color: #b5b5b5;
            }
            QTableWidget {
                background-color: #484848;
                border: 1px solid #555555;
                border-radius: 4px;
                gridline-color: transparent;
                selection-background-color: #1e4976;
                selection-color: #ffffff;
                color: #dedede;
                alternate-background-color: #525252;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 12px;
            }
            QTableWidget::item {
                padding: 4px 8px;
                border: none;
            }
            QTableWidget::item:selected {
                background-color: #1e4976;
            }
            QHeaderView::section {
                background-color: #383838;
                color: #d6d6d6;
                padding: 6px 8px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-weight: bold;
                font-size: 14px;
                border: none;
                border-bottom: 1px solid #4f4f4f;
            }
            QHeaderView::section:hover {
                background-color: #444444;
            }
            QPushButton {
                background-color: #525252;
                color: #dedede;
                border: 1px solid #686868;
                border-radius: 4px;
                padding: 6px 14px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-weight: 500;
                font-size: 14px;
                min-height: 22px;
                outline: none;
            }
            QPushButton:hover {
                background-color: #5f5f5f;
                border-color: #7d7d7d;
            }
            QPushButton:pressed {
                background-color: #3a3a3a;
            }
            QPushButton:disabled {
                background-color: #3b3b3b;
                color: #777777;
                border-color: #484848;
            }
            QPushButton#btnFixDuplicates {
                background-color: #484848;
                color: #dedede;
                border: 1px solid #686868;
                outline: none;
            }
            QPushButton#btnFixDuplicates:hover {
                background-color: #5c452b;
                border-color: #e67e22;
                color: #ffffff;
            }
            QPushButton#btnFixDuplicates:disabled {
                background-color: #3b3b3b;
                color: #777777;
                border-color: #484848;
            }
            QPushButton#btnLock {
                font-size: 15px;
                padding: 0px;
                min-width: 30px;
                max-width: 30px;
                min-height: 30px;
                max-height: 30px;
                border-radius: 4px;
                background-color: #484848;
                border: 1px solid #5a5a5a;
                outline: none;
            }
            QPushButton#btnLock:hover {
                background-color: #555555;
                border: 1px solid #707070;
            }
            QPushButton#btnLock:pressed {
                background-color: #383838;
            }
            QPushButton#btnLock:checked {
                background-color: #484848;
                border: 1px solid #5a5a5a;
            }
            QPushButton#btnLock:checked:hover {
                background-color: #555555;
                border: 1px solid #707070;
            }
            QPushButton#btnLock:checked:pressed {
                background-color: #383838;
            }
            QPushButton#btnApply {
                background-color: #1e9bfd;
                color: #ffffff;
                border: 1px solid #168de6;
                font-weight: bold;
                font-size: 14px;
                padding: 7px 18px;
            }
            QPushButton#btnApply:hover {
                background-color: #168de6;
            }
            QPushButton#btnApply:pressed {
                background-color: #0f7fcf;
            }
            QCheckBox {
                color: #d0d0d0;
                spacing: 8px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 14px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 1px solid #666666;
                background-color: #383838;
            }
            QCheckBox::indicator:hover {
                border: 1px solid #888888;
                background-color: #424242;
            }
            QCheckBox::indicator:checked {
                background-color: #1e9bfd;
                border: 1px solid #1e9bfd;
                image: url("{check_icon}");
            }
            QCheckBox::indicator:checked:hover {
                background-color: #168de6;
                border: 1px solid #168de6;
            }
            QProgressBar {
                border: 1px solid #555555;
                border-radius: 4px;
                text-align: center;
                background-color: #333333;
                color: #ffffff;
                height: 14px;
            }
            QProgressBar::chunk {
                background-color: #1e9bfd;
                border-radius: 3px;
            }
        """.replace("{check_icon}", check_icon)
        self.setStyleSheet(style)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(8)

        self.header_frame = QFrame(self)
        self.header_frame.setObjectName("headerFrame")
        self.header_frame.setCursor(Qt.PointingHandCursor)
        self.header_frame.setToolTip("Click to open and select this Multi-Material in Slate Material Editor")
        self.header_frame.mousePressEvent = lambda event: self.open_target_material_in_sme() if event.button() == Qt.LeftButton else None

        header_layout = QHBoxLayout(self.header_frame)
        header_layout.setContentsMargins(4, 4, 4, 4)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        self.lbl_mat_name = QLabel("", self)
        self.lbl_mat_name.setObjectName("matTitle")
        self.lbl_mat_name.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self.lbl_slot_count = QLabel("Slots: - | Used in scene: -", self)
        self.lbl_slot_count.setObjectName("slotCountLabel")
        self.lbl_slot_count.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        info_layout.addWidget(self.lbl_mat_name)
        info_layout.addWidget(self.lbl_slot_count)
        header_layout.addLayout(info_layout, 1)

        top_layout.addWidget(self.header_frame, 1)

        self.btn_lock = QPushButton("", self)
        self.btn_lock.setObjectName("btnLock")
        self.btn_lock.setCheckable(True)
        self.btn_lock.setChecked(False)
        self.btn_lock.setFocusPolicy(Qt.NoFocus)
        self.btn_lock.setFixedSize(30, 30)
        self.btn_lock.setIcon(get_lock_icon(False))
        self.btn_lock.setIconSize(QSize(18, 18))
        self.btn_lock.setToolTip("Lock Material: OFF\nClick to lock the current material and prevent viewport selection changes from replacing it.")
        self.btn_lock.clicked.connect(self.toggle_lock)
        top_layout.addWidget(self.btn_lock, 0, Qt.AlignVCenter)

        main_layout.addLayout(top_layout)

        self.table = ReorderableTableWidget(self)
        self.custom_header = CustomHeaderView(Qt.Horizontal, self.table)
        self.table.setHorizontalHeader(self.custom_header)
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["ID", "Color", "Name", "Sub-Material", "On", "Used Faces"])
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setItemDelegate(UnifiedTableItemDelegate(self.table))

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.sectionClicked.connect(self.on_header_section_clicked)

        self.table.setColumnWidth(0, 54)
        self.table.setColumnWidth(1, 52)
        self.table.setColumnWidth(4, 44)
        self.table.setRowHeight(0, 31)

        self.table.cellChanged.connect(self.on_table_cell_changed)
        self.table.cellClicked.connect(self.on_table_cell_clicked)
        self.table.cellDoubleClicked.connect(self.on_table_cell_double_clicked)
        main_layout.addWidget(self.table, 1)

        tools_layout = QHBoxLayout()
        tools_layout.setSpacing(6)

        self.btn_add = QPushButton("➕ Add", self)
        self.btn_add.setToolTip("Add a new empty slot at the end of the material list")
        self.btn_add.clicked.connect(self.add_slot)
        tools_layout.addWidget(self.btn_add)

        self.btn_remove = QPushButton("➖ Delete", self)
        self.btn_remove.setToolTip("Remove the currently selected slot from the material")
        self.btn_remove.clicked.connect(self.remove_selected_slot)
        tools_layout.addWidget(self.btn_remove)

        self.btn_duplicate = QPushButton("Duplicate", self)
        self.btn_duplicate.setToolTip("Duplicate the selected slot with its properties")
        self.btn_duplicate.clicked.connect(self.duplicate_selected_slot)
        tools_layout.addWidget(self.btn_duplicate)

        tools_layout.addStretch(1)

        self.btn_fix_duplicates = QPushButton("Fix Duplicates", self)
        self.btn_fix_duplicates.setObjectName("btnFixDuplicates")
        self.btn_fix_duplicates.setToolTip("Find duplicate sub-materials (e.g. from Attach), merge them into single slots, and remap geometry face IDs")
        self.btn_fix_duplicates.clicked.connect(self.fix_duplicates)
        tools_layout.addWidget(self.btn_fix_duplicates)

        main_layout.addLayout(tools_layout)
        main_layout.addSpacing(6)

        options_layout = QHBoxLayout()
        options_layout.setSpacing(18)

        config_settings = load_config_settings()

        self.chk_auto_renumber = QCheckBox("Auto-Renumber IDs", self)
        self.chk_auto_renumber.setChecked(config_settings.get('auto_renumber_ids', True))
        self.chk_auto_renumber.setToolTip("Automatically renumbers Material IDs (1..N) according to slot order on drag & drop")
        self.chk_auto_renumber.toggled.connect(self.save_checkbox_settings)
        options_layout.addWidget(self.chk_auto_renumber)

        self.chk_sync_names = QCheckBox("Sync Names", self)
        self.chk_sync_names.setChecked(config_settings.get('sync_names', True))
        self.chk_sync_names.setToolTip("When editing slot names, automatically renames the assigned sub-material in 3ds Max")
        self.chk_sync_names.toggled.connect(self.save_checkbox_settings)
        options_layout.addWidget(self.chk_sync_names)

        self.chk_update_faces = WarningSuffixCheckBox("Update IDs on Geometry", self)
        self.chk_update_faces.setChecked(config_settings.get('update_ids_on_geometry', False))
        self.chk_update_faces.setToolTip("Reassigns face Material IDs on scene geometry to match updated slot positions")
        self.chk_update_faces.toggled.connect(self.save_checkbox_settings)
        options_layout.addWidget(self.chk_update_faces)

        options_layout.addStretch(1)

        self.btn_close = QPushButton("Close", self)
        self.btn_close.clicked.connect(self.close)
        options_layout.addWidget(self.btn_close)

        main_layout.addLayout(options_layout)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        # Debug Live Sync widgets (commented out for clean native UI experience; uncomment for debugging)
        # bottom_layout = QHBoxLayout()
        # self.btn_toggle_sync = QPushButton("● Live Sync Active", self)
        # self.btn_toggle_sync.clicked.connect(self.toggle_live_sync)
        # bottom_layout.addWidget(self.btn_toggle_sync, 1)
        # self.btn_apply = QPushButton("Apply Changes", self)
        # self.btn_apply.setObjectName("btnApply")
        # self.btn_apply.clicked.connect(self.apply_changes)
        # bottom_layout.addWidget(self.btn_apply)
        # main_layout.addLayout(bottom_layout)
        # self.update_sync_ui_state()

    def toggle_live_sync(self):
        self.is_live_sync = not self.is_live_sync
        self.update_sync_ui_state()

        if self.is_live_sync:
            if self.target_material:
                self.sync_to_max("Resume Live Sync", update_geom=self.chk_update_faces.isChecked())
        else:
            self.set_status("● Live Sync Paused")

    def update_sync_ui_state(self):
        if not hasattr(self, 'btn_toggle_sync') or self.btn_toggle_sync is None:
            return
        if self.is_live_sync:
            self.btn_toggle_sync.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    border: 1px solid transparent;
                    color: #5bb4f8;
                    font-family: 'Segoe UI', Arial, sans-serif;
                    font-weight: 500;
                    font-size: 14px;
                    text-align: left;
                    padding: 4px 6px;
                }
                QPushButton:hover {
                    background-color: #3b3b3b;
                    border-radius: 4px;
                }
            """)
            self.btn_toggle_sync.setToolTip("Live Sync is active: Changes in the table are immediately synchronized with 3ds Max.\nClick to pause and switch to manual Apply mode.")
            if hasattr(self, 'btn_apply') and self.btn_apply is not None:
                self.btn_apply.setVisible(False)
            self.set_status(self._current_status_text)
        else:
            self.btn_toggle_sync.setStyleSheet("""
                QPushButton {
                    background-color: #525252;
                    border: 1px solid #686868;
                    border-radius: 4px;
                    color: #ffc107;
                    font-family: 'Segoe UI', Arial, sans-serif;
                    font-weight: bold;
                    font-size: 14px;
                    text-align: left;
                    padding: 4px 10px;
                }
                QPushButton:hover {
                    background-color: #5f5f5f;
                    border-color: #7d7d7d;
                }
            """)
            self.btn_toggle_sync.setToolTip("Live Sync is paused: Changes are kept locally.\nClick 'Apply Changes' to save or click here to resume Live Sync.")
            if hasattr(self, 'btn_apply') and self.btn_apply is not None:
                self.btn_apply.setVisible(True)
            self.btn_toggle_sync.setText("● Live Sync Paused")

    def set_status(self, text):
        self._current_status_text = text
        if hasattr(self, 'btn_toggle_sync') and self.btn_toggle_sync is not None and self.is_live_sync:
            self.btn_toggle_sync.setText(text)

    def toggle_lock(self, checked=None):
        if checked is None:
            self.is_locked = not self.is_locked
        else:
            self.is_locked = bool(checked)

        if hasattr(self, 'btn_lock') and self.btn_lock is not None:
            self.btn_lock.setChecked(self.is_locked)
            self.btn_lock.setIcon(get_lock_icon(self.is_locked))
            if self.is_locked:
                self.btn_lock.setToolTip("Lock Material: ON\nCurrent material is locked. Viewport selection changes will not replace it.\nClick to unlock.")
            else:
                self.btn_lock.setToolTip("Lock Material: OFF\nClick to lock the current material and prevent viewport selection changes from replacing it.")

        if not self.is_locked and rt:
            self.check_selection_and_material_changes()

    def check_selection_and_material_changes(self):
        if not rt or self.is_loading:
            return
        if self._preview_duplicate_groups is not None:
            return
        if self.table._is_dragging or self.table.state() == QAbstractItemView.EditingState:
            return

        current_sel_handles = []
        try:
            if rt.selection and rt.selection.count > 0:
                current_sel_handles = [int(rt.getHandleByAnim(obj)) for obj in rt.selection if rt.isValidNode(obj)]
        except Exception:
            current_sel_handles = []

        selection_changed = (current_sel_handles != self._last_sel_handles)
        self._last_sel_handles = current_sel_handles

        # If material is locked and we already have a material loaded
        if self.is_locked and self.target_material is not None:
            try:
                if not rt.isValidObj(self.target_material):
                    self.clear_ui()
                    return
                current_fp = str(rt._jsh_MME_GetMatFingerprint(self.target_material))
            except Exception:
                current_fp = ""

            if self.is_live_sync and current_fp != self._last_fingerprint:
                self._last_fingerprint = current_fp
                is_multi = False
                try:
                    is_multi = bool(rt.isKindOf(self.target_material, rt.Multimaterial) or rt.isKindOf(self.target_material, rt.multiSubMaterial))
                except Exception:
                    is_multi = False
                if is_multi:
                    cur_row = self.table.currentRow()
                    self.load_material(self.target_material)
                    if 0 <= cur_row < self.table.rowCount():
                        self.table.selectRow(cur_row)
                else:
                    self.load_single_material(self.target_material)
            else:
                self.update_button_states()
            return

        # Unlocked, or locked with no material loaded yet (waiting for first selection)
        try:
            detected_mat = rt._jsh_MME_GetSelectedMaterial()
            if str(detected_mat) == "undefined" or detected_mat is None:
                detected_mat = None
        except Exception:
            detected_mat = None

        if detected_mat is None:
            if self._current_mat_handle != 0 or self.target_material is not None:
                self.clear_ui()
            else:
                self.update_button_states()
            return

        try:
            mat_handle = int(rt._jsh_MME_GetMatHandle(detected_mat))
        except Exception:
            mat_handle = 0

        if mat_handle == 0:
            if self._current_mat_handle != 0 or self.target_material is not None:
                self.clear_ui()
            return

        try:
            current_fp = str(rt._jsh_MME_GetMatFingerprint(detected_mat))
        except Exception:
            current_fp = ""

        is_multi = False
        try:
            is_multi = bool(rt.isKindOf(detected_mat, rt.Multimaterial) or rt.isKindOf(detected_mat, rt.multiSubMaterial))
        except Exception:
            is_multi = False

        if is_multi:
            if mat_handle != self._current_mat_handle:
                self._current_mat_handle = mat_handle
                self.load_material(detected_mat)
            elif selection_changed and len(current_sel_handles) > 0:
                # Reselected object(s) or selection changed in viewport: refresh material and scene object counts
                self._last_fingerprint = current_fp
                cur_row = self.table.currentRow()
                self.load_material(detected_mat)
                if 0 <= cur_row < self.table.rowCount():
                    self.table.selectRow(cur_row)
            elif self.is_live_sync and current_fp != self._last_fingerprint:
                self._last_fingerprint = current_fp
                cur_row = self.table.currentRow()
                self.load_material(detected_mat)
                if 0 <= cur_row < self.table.rowCount():
                    self.table.selectRow(cur_row)
            else:
                self.update_button_states()
        else:
            # Single / Non-Multi Material (e.g. PhysicalMaterial, VRayMtl, CoronaPhysicalMtl, etc.)
            if mat_handle != self._current_mat_handle or (selection_changed and len(current_sel_handles) > 0):
                self._current_mat_handle = mat_handle
                self._last_fingerprint = current_fp
                self.load_single_material(detected_mat)
            elif current_fp != self._last_fingerprint:
                self._last_fingerprint = current_fp
                self.load_single_material(detected_mat)
            else:
                self.update_button_states()

    def clear_ui(self):
        self.target_material = None
        self._current_mat_handle = 0
        self._last_fingerprint = ""
        self.slots_data = []
        self.initial_id_map = {}
        self._preview_duplicate_groups = None
        self._backup_slots_data = None
        self._current_scene_objs_using_mat = []
        self.is_loading = True
        self.table.setRowCount(0)
        self.lbl_mat_name.setText("")
        self.lbl_slot_count.setText("Slots: - | Used in scene: -")
        if hasattr(self, 'header_frame'):
            self.header_frame.setToolTip("")
        self.set_status("● Waiting for selection...")
        self.update_button_states()
        self.is_loading = False

    def load_single_material(self, mat):
        """Displays single (non-multi) material info and enables fast pick to SME."""
        self.target_material = mat
        if not mat or not rt:
            return

        self.is_loading = True
        try:
            mat_name = getattr(mat, 'name', 'Material')
            try:
                self._current_mat_handle = int(rt._jsh_MME_GetMatHandle(mat))
            except Exception:
                self._current_mat_handle = 0

            try:
                self._last_fingerprint = str(rt._jsh_MME_GetMatFingerprint(mat))
            except Exception:
                self._last_fingerprint = ""

            try:
                mat_class = str(rt.classOf(mat))
            except Exception:
                mat_class = "Material"

            scene_objs = self.get_objects_using_material(mat)
            self._current_scene_objs_using_mat = scene_objs

            self.lbl_mat_name.setText(mat_name)
            self.lbl_slot_count.setText("Type: {} | Used in scene: {} object(s)".format(mat_class, len(scene_objs)))
            if hasattr(self, 'header_frame'):
                self.header_frame.setToolTip("Click to open and select '{}' ({}) in Slate Material Editor".format(mat_name, mat_class))

            self.slots_data = []
            self.initial_id_map = {}
            self.table.setRowCount(0)
            self.set_status("● Single Material: '{}' ({})".format(mat_name, mat_class))
            self.update_button_states()

        except Exception as e:
            traceback.print_exc()
        finally:
            self.is_loading = False

    def load_material(self, mat):
        self.target_material = mat
        if not mat or not rt:
            return

        self.is_loading = True
        try:
            mat_name = getattr(mat, 'name', 'Multi/Sub-Object')

            try:
                self._current_mat_handle = int(rt._jsh_MME_GetMatHandle(mat))
            except Exception:
                self._current_mat_handle = 0

            try:
                self._last_fingerprint = str(rt._jsh_MME_GetMatFingerprint(mat))
            except Exception:
                self._last_fingerprint = ""

            if not hasattr(rt, '_jsh_MME_GetMultiMatData') or rt._jsh_MME_GetMultiMatData is None:
                init_maxscript_helpers()

            if not rt or not hasattr(rt, '_jsh_MME_GetMultiMatData') or rt._jsh_MME_GetMultiMatData is None:
                self.is_loading = False
                return

            raw_slots = rt._jsh_MME_GetMultiMatData(mat)
            if raw_slots is None or str(raw_slots) == "undefined":
                self.is_loading = False
                return

            num_subs = len(raw_slots)
            scene_objs = self.get_objects_using_material(mat)
            self._current_scene_objs_using_mat = scene_objs
            id_face_counts = self.count_faces_per_id(scene_objs)

            self.lbl_mat_name.setText(mat_name)
            self.lbl_slot_count.setText("Slots: {} | Used in scene: {} object(s)".format(num_subs, len(scene_objs)))
            if hasattr(self, 'header_frame'):
                self.header_frame.setToolTip("Click to open and select '{}' in Slate Material Editor".format(mat_name))

            self.slots_data = []
            self.initial_id_map = {}

            for i in range(num_subs):
                slot_arr = raw_slots[i]
                slot_id = int(slot_arr[0])
                slot_name = str(slot_arr[1])
                sub_mat = slot_arr[2]
                if str(sub_mat) == "undefined" or sub_mat is None:
                    sub_mat = None

                sub_mat_name = str(slot_arr[3])
                sub_mat_class = str(slot_arr[4])
                is_enabled = bool(slot_arr[5])

                col_arr = slot_arr[6]
                r, g, b = int(col_arr[0]), int(col_arr[1]), int(col_arr[2])
                color = linear_to_srgb_color(r, g, b)

                if (not slot_name or slot_name.strip() == "") and sub_mat and sub_mat_name not in ("(None)", "None", ""):
                    slot_name = sub_mat_name

                face_count = id_face_counts.get(slot_id, 0)

                slot_entry = {
                    'initial_id': slot_id,
                    'id': slot_id,
                    'name': slot_name,
                    'sub_mat': sub_mat,
                    'sub_mat_name': sub_mat_name if sub_mat else 'None',
                    'sub_mat_class': sub_mat_class,
                    'enabled': is_enabled,
                    'color': color,
                    'face_count': face_count
                }
                self.slots_data.append(slot_entry)
                self.initial_id_map[i] = slot_id

            self.populate_table()
            self.set_status("● Live Sync Active")
            self.update_button_states()

        except Exception as e:
            traceback.print_exc()
        finally:
            self.is_loading = False

    def load_mock_data(self):
        """Loads sample mock data for standalone testing outside 3ds Max."""
        self.is_loading = True
        self._current_scene_objs_using_mat = []
        self.slots_data = [
            {'initial_id': 1, 'id': 1, 'name': 'M_Wall_Paint_01', 'sub_mat': None, 'sub_mat_name': 'M_Wall_Paint_01', 'sub_mat_class': 'VRayMtl', 'enabled': True, 'color': QColor(220, 215, 205), 'face_count': 342},
            {'initial_id': 2, 'id': 2, 'name': 'M_Floor_Wood_Oak', 'sub_mat': None, 'sub_mat_name': 'M_Floor_Wood_Oak', 'sub_mat_class': 'CoronaPhysicalMtl', 'enabled': True, 'color': QColor(160, 110, 60), 'face_count': 128},
            {'initial_id': 3, 'id': 3, 'name': 'M_Ceiling_White', 'sub_mat': None, 'sub_mat_name': 'M_Ceiling_White', 'sub_mat_class': 'VRayMtl', 'enabled': True, 'color': QColor(240, 240, 240), 'face_count': 64},
            {'initial_id': 4, 'id': 4, 'name': '', 'sub_mat': None, 'sub_mat_name': 'None', 'sub_mat_class': 'None', 'enabled': True, 'color': None, 'face_count': 0},
            {'initial_id': 5, 'id': 5, 'name': 'M_Window_Frame_Black', 'sub_mat': None, 'sub_mat_name': 'M_Window_Frame_Black', 'sub_mat_class': 'PhysicalMaterial', 'enabled': True, 'color': QColor(30, 30, 30), 'face_count': 96},
        ]
        self.lbl_mat_name.setText("Mock_MultiMaterial_Demo")
        self.lbl_slot_count.setText("Slots: 5 (Test Mode)")
        if hasattr(self, 'header_frame'):
            self.header_frame.setToolTip("Click to open and select 'Mock_MultiMaterial_Demo' in Slate Material Editor")
        self.populate_table()
        self.is_loading = False

    def get_objects_using_material(self, target_mat):
        """Finds all scene geometry objects referencing target_mat."""
        if not rt or not target_mat:
            return []
        objs = []
        try:
            target_handle = int(rt._jsh_MME_GetMatHandle(target_mat))
            if target_handle == 0:
                return []
            for obj in list(rt.objects):
                if rt.isValidNode(obj):
                    mat = getattr(obj, 'material', None)
                    if mat is not None and str(mat) != "undefined":
                        try:
                            if int(rt._jsh_MME_GetMatHandle(mat)) == target_handle:
                                objs.append(obj)
                        except Exception:
                            if mat == target_mat:
                                objs.append(obj)
        except Exception:
            pass
        return objs

    def count_faces_per_id(self, scene_objs):
        """Calculates total face counts per Material ID across objects."""
        counts = {}
        if not rt or not scene_objs:
            return counts

        try:
            for obj in scene_objs:
                id_counts = rt._jsh_MME_GetFaceIDCounts(obj)
                if id_counts:
                    for entry in list(id_counts):
                        fid = int(entry[0])
                        num_faces = int(entry[1])
                        counts[fid] = counts.get(fid, 0) + num_faces
        except Exception:
            pass

        return counts

    def sync_to_max(self, action_name="Update MultiMaterial", update_geom=False):
        """Synchronizes all slot data to 3ds Max Multi-Material with Undo support."""
        if not self.target_material or not rt:
            return

        rt.theHold.Begin()
        try:
            mat = self.target_material
            count = len(self.slots_data)

            submats_arr = rt.execute("#()")
            names_arr = rt.execute("#()")
            ids_arr = rt.execute("#()")
            enableds_arr = rt.execute("#()")

            for slot in self.slots_data:
                sub_mat = slot['sub_mat'] if slot['sub_mat'] is not None else rt.undefined
                rt.append(submats_arr, sub_mat)
                rt.append(names_arr, str(slot['name']))
                rt.append(ids_arr, int(slot['id']))
                rt.append(enableds_arr, bool(slot['enabled']))

            rt._jsh_MME_ApplyMultiMatData(mat, count, submats_arr, names_arr, ids_arr, enableds_arr)

            faces_updated_count = 0
            if update_geom and self.chk_update_faces.isChecked():
                id_mapping = {}
                for slot in self.slots_data:
                    init_id = slot.get('initial_id')
                    current_id = slot.get('id')
                    if init_id is not None and init_id != current_id:
                        id_mapping[init_id] = current_id

                if id_mapping:
                    scene_objs = self.get_objects_using_material(mat)
                    if scene_objs:
                        old_keys = list(id_mapping.keys())
                        new_vals = [id_mapping[k] for k in old_keys]
                        old_ids_str = ", ".join(str(k) for k in old_keys)
                        new_ids_str = ", ".join(str(v) for v in new_vals)
                        old_ids_arr = rt.execute("#({})".format(old_ids_str))
                        new_ids_arr = rt.execute("#({})".format(new_ids_str))
                        for obj in scene_objs:
                            try:
                                faces_updated_count += int(rt._jsh_MME_UpdateFaceIDs(obj, old_ids_arr, new_ids_arr))
                            except Exception as err:
                                print("Error updating face IDs on object {}: {}".format(getattr(obj, 'name', 'obj'), err))

            rt.theHold.Accept(action_name)
            if faces_updated_count > 0:
                self.set_status("● Live Sync: {} ({} faces)".format(action_name, faces_updated_count))
            else:
                self.set_status("● Live Sync: {}".format(action_name))

            for s in self.slots_data:
                s['initial_id'] = s['id']

            try:
                self._last_fingerprint = str(rt._jsh_MME_GetMatFingerprint(mat))
            except Exception:
                pass

        except Exception as e:
            rt.theHold.Cancel()
            print("Live Sync Error: {}".format(e))

    def apply_changes(self):
        if not self.target_material or not rt:
            QMessageBox.information(self, "Apply Changes", "Changes applied (Standalone test mode).")
            return

        # If Sync Names is checked, rename any sub-materials that were changed while paused
        if self.chk_sync_names.isChecked():
            for slot in self.slots_data:
                sub_mat = slot.get('sub_mat')
                if sub_mat and slot.get('name'):
                    try:
                        if str(getattr(sub_mat, 'name', '')) != str(slot['name']):
                            sub_mat.name = str(slot['name'])
                            slot['sub_mat_name'] = str(slot['name'])
                    except Exception:
                        pass

        # Apply any sub-material colors that were changed while paused
        for slot in self.slots_data:
            sub_mat = slot.get('sub_mat')
            color = slot.get('color')
            if sub_mat and color:
                try:
                    lin_r, lin_g, lin_b = srgb_to_linear_rgb(color)
                    rt._jsh_MME_SetSubMaterialColor(sub_mat, lin_r, lin_g, lin_b)
                except Exception:
                    pass

        self.sync_to_max("Apply MultiMaterial Changes", update_geom=self.chk_update_faces.isChecked())
        QMessageBox.information(self, "Success", "Successfully applied all changes to '{}'.".format(getattr(self.target_material, 'name', 'MultiMaterial')))

    def update_duplicate_ids(self):
        id_counts = {}
        for s in self.slots_data:
            sid = s.get('id')
            if sid is not None:
                id_counts[sid] = id_counts.get(sid, 0) + 1
        self._duplicate_ids = {sid for sid, count in id_counts.items() if count > 1}
        if hasattr(self, 'table') and hasattr(self.table, 'horizontalHeader'):
            self.table.horizontalHeader().viewport().update()

    def on_header_section_clicked(self, logicalIndex):
        if logicalIndex == 0:
            self.sort_by_id()

    def sort_by_id(self):
        if not self.slots_data or len(self.slots_data) < 2:
            return

        is_asc = all(self.slots_data[i]['id'] <= self.slots_data[i+1]['id'] for i in range(len(self.slots_data)-1))

        if is_asc:
            self.slots_data.sort(key=lambda s: s.get('id', 0), reverse=True)
            sort_dir = "Descending"
        else:
            self.slots_data.sort(key=lambda s: s.get('id', 0))
            sort_dir = "Ascending"

        self.populate_table()

        if self.is_live_sync:
            self.sync_to_max("Sort Slots by ID ({})".format(sort_dir), update_geom=False)
        else:
            self.set_status("● Paused: Slots sorted by ID ({})".format(sort_dir))

    def populate_table(self):
        self.is_loading = True
        self.update_duplicate_ids()
        self.table.setRowCount(len(self.slots_data))

        for row, slot in enumerate(self.slots_data):
            id_item = QTableWidgetItem(str(slot['id']))
            id_item.setTextAlignment(Qt.AlignCenter)
            id_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
            id_item.setToolTip("Double-click to edit Material ID")
            self.table.setItem(row, 0, id_item)

            swatch_item = QTableWidgetItem()
            swatch_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            swatch_item.setToolTip("Click to change diffuse color")
            self.table.setItem(row, 1, swatch_item)

            name_item = QTableWidgetItem(slot['name'])
            name_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
            name_item.setToolTip("Double-click to edit slot name")
            self.table.setItem(row, 2, name_item)

            sub_text = slot['sub_mat_name']
            if slot['sub_mat_class'] and slot['sub_mat_class'] != 'None':
                sub_text += "  ({})".format(slot['sub_mat_class'])
            sub_item = QTableWidgetItem(sub_text)
            sub_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            if slot.get('sub_mat'):
                sub_item.setToolTip("Click to open and select '{}' in Slate Material Editor".format(slot.get('sub_mat_name', 'Sub-Material')))
            else:
                sub_item.setToolTip("No sub-material assigned to this slot")
            self.table.setItem(row, 3, sub_item)

            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            chk_item.setToolTip("Click to enable/disable slot")
            self.table.setItem(row, 4, chk_item)

            used_faces = slot.get('face_count', 0)
            used_text = str(used_faces) if used_faces > 0 else "-"
            used_item = QTableWidgetItem(used_text)
            used_item.setTextAlignment(Qt.AlignCenter)
            used_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 5, used_item)

            self.table.setRowHeight(row, 31)

        self.update_button_states()
        self.is_loading = False

    def on_table_cell_clicked(self, row, column):
        if self.table._is_dragging:
            return
        if column == 1:
            self.pick_slot_color(row)
        elif column == 3:
            self.open_submaterial_in_sme(row)

    def on_table_cell_double_clicked(self, row, column):
        if self.table._is_dragging:
            return
        if column == 3:
            self.open_submaterial_in_sme(row)

    def open_submaterial_in_sme(self, row):
        if row < 0 or row >= len(self.slots_data):
            return

        slot = self.slots_data[row]
        sub_mat = slot.get('sub_mat')

        if not sub_mat:
            self.set_status("● Slot #{} has no sub-material assigned".format(slot.get('id', row + 1)))
            return

        if rt:
            try:
                if not hasattr(rt, '_jsh_MME_OpenInSME') or rt._jsh_MME_OpenInSME is None:
                    init_maxscript_helpers()

                success = bool(rt._jsh_MME_OpenInSME(sub_mat))
                if success:
                    self.set_status("● Slate Editor: Focused '{}'".format(slot.get('sub_mat_name', 'Material')))
                else:
                    self.set_status("● Slate Material Editor opened")
            except Exception as e:
                print("Error opening material in SME: {}".format(e))
                self.set_status("● Error opening Slate Material Editor")
        else:
            self.set_status("● Slate Editor: Focused '{}' (Test Mode)".format(slot.get('sub_mat_name', 'Material')))

    def open_target_material_in_sme(self):
        if not self.target_material:
            return
        if rt:
            try:
                if not hasattr(rt, '_jsh_MME_OpenInSME') or rt._jsh_MME_OpenInSME is None:
                    init_maxscript_helpers()

                success = bool(rt._jsh_MME_OpenInSME(self.target_material))
                mat_name = getattr(self.target_material, 'name', 'MultiMaterial')
                if success:
                    self.set_status("● Slate Editor: Focused '{}'".format(mat_name))
                else:
                    self.set_status("● Slate Material Editor opened")
            except Exception as e:
                print("Error opening material in SME: {}".format(e))
                self.set_status("● Error opening Slate Material Editor")
        else:
            mat_name = self.lbl_mat_name.text()
            self.set_status("● Slate Editor: Focused '{}' (Test Mode)".format(mat_name))

    def pick_slot_color(self, row):
        if row < 0 or row >= len(self.slots_data):
            return

        slot = self.slots_data[row]
        sub_mat = slot.get('sub_mat')

        if not sub_mat:
            QMessageBox.information(
                self,
                "No Sub-Material",
                "This slot does not have a sub-material assigned to change its color."
            )
            return

        current_color = slot.get('color') or QColor(128, 128, 128)
        new_color = QColorDialog.getColor(
            current_color,
            self,
            "Select Material Diffuse Color"
        )

        if new_color.isValid():
            slot['color'] = new_color
            self.table.viewport().update()

            if not self.is_live_sync:
                self.set_status("● Paused: Color changed")
                return

            lin_r, lin_g, lin_b = srgb_to_linear_rgb(new_color)

            if rt:
                rt.theHold.Begin()
                try:
                    rt._jsh_MME_SetSubMaterialColor(sub_mat, lin_r, lin_g, lin_b)
                    if self.target_material:
                        try:
                            rt.notifyDependents(self.target_material)
                            for obj in self.get_objects_using_material(self.target_material):
                                try:
                                    rt.update(obj)
                                    rt.notifyDependents(obj)
                                except Exception:
                                    pass
                        except Exception:
                            pass
                    try:
                        rt.redrawViews()
                    except Exception:
                        pass
                    rt.theHold.Accept("Change Material Color")
                    self.set_status("● Live Sync: Color updated")
                    try:
                        self._last_fingerprint = str(rt._jsh_MME_GetMatFingerprint(self.target_material))
                    except Exception:
                        pass
                except Exception as e:
                    rt.theHold.Cancel()
                    print("Error setting material color: {}".format(e))

    def move_row_data_live(self, source_row, target_row, refresh_ui=True):
        if source_row == target_row or source_row < 0 or source_row >= len(self.slots_data):
            return
        if target_row < 0 or target_row >= len(self.slots_data):
            return

        item_to_move = self.slots_data.pop(source_row)
        self.slots_data.insert(target_row, item_to_move)

        if self.chk_auto_renumber.isChecked():
            for idx, s in enumerate(self.slots_data):
                s['id'] = idx + 1

        if refresh_ui:
            self.populate_table()

    def finish_drag_reorder(self, target_row=None):
        self.populate_table()
        if target_row is not None and 0 <= target_row < len(self.slots_data):
            self.table.selectRow(target_row)
        else:
            current_row = self.table.currentRow()
            if 0 <= current_row < len(self.slots_data):
                self.table.selectRow(current_row)

        if self.is_live_sync:
            self.sync_to_max("Reorder Slots", update_geom=True)
        else:
            self.set_status("● Paused: Slots reordered")

    def force_renumber_ids(self, refresh_table=True, sync=True):
        for idx, slot in enumerate(self.slots_data):
            slot['id'] = idx + 1
        if refresh_table:
            self.populate_table()
        if sync:
            if self.is_live_sync:
                self.sync_to_max("Renumber IDs", update_geom=self.chk_update_faces.isChecked())
            else:
                self.set_status("● Paused: IDs renumbered")

    def on_table_cell_changed(self, row, column):
        if self.is_loading or row >= len(self.slots_data):
            return

        slot = self.slots_data[row]

        if column == 0:
            id_item = self.table.item(row, 0)
            if id_item:
                try:
                    new_id = int(id_item.text().strip())
                    slot['id'] = new_id
                    self.update_duplicate_ids()
                    self.table.viewport().update()
                    if self.is_live_sync and self.target_material and rt:
                        if self.chk_update_faces.isChecked():
                            self.sync_to_max("Change Slot ID", update_geom=True)
                        else:
                            try:
                                rt._jsh_MME_SetSlotID(self.target_material, row + 1, new_id)
                                self.set_status("● Live Sync: ID changed")
                                try:
                                    self._last_fingerprint = str(rt._jsh_MME_GetMatFingerprint(self.target_material))
                                except Exception:
                                    pass
                            except Exception:
                                self.sync_to_max("Change Slot ID", update_geom=False)
                    else:
                        self.set_status("● Paused: ID changed")
                except ValueError:
                    id_item.setText(str(slot['id']))

        elif column == 2:
            name_item = self.table.item(row, 2)
            if name_item:
                new_name = name_item.text()
                slot['name'] = new_name

                if self.chk_sync_names.isChecked():
                    slot['sub_mat_name'] = new_name
                    sub_text = new_name
                    if slot.get('sub_mat_class') and slot['sub_mat_class'] != 'None':
                        sub_text += "  ({})".format(slot['sub_mat_class'])
                    sub_item = self.table.item(row, 3)
                    if sub_item:
                        sub_item.setText(sub_text)

                self.table.viewport().update()

                if self.is_live_sync and self.target_material and rt:
                    try:
                        sync_sub = bool(self.chk_sync_names.isChecked() and slot.get('sub_mat') is not None)
                        rt._jsh_MME_SetSlotName(self.target_material, row + 1, new_name, sync_sub)
                        self.set_status("● Live Sync: Slot renamed")
                        try:
                            self._last_fingerprint = str(rt._jsh_MME_GetMatFingerprint(self.target_material))
                        except Exception:
                            pass
                    except Exception as e:
                        print("Error setting slot name: {}".format(e))
                elif not self.is_live_sync:
                    self.set_status("● Paused: Slot renamed")

    def add_slot(self):
        if not self.target_material:
            return
        next_id = len(self.slots_data) + 1
        new_slot = {
            'initial_id': None,
            'id': next_id,
            'name': '',
            'sub_mat': None,
            'sub_mat_name': 'None',
            'sub_mat_class': 'None',
            'enabled': True,
            'color': None,
            'face_count': 0
        }
        self.slots_data.append(new_slot)
        self.populate_table()
        self.table.selectRow(len(self.slots_data) - 1)
        if self.is_live_sync:
            self.sync_to_max("Add Slot", update_geom=False)
        else:
            self.set_status("● Paused: Slot added")

    def remove_selected_slot(self):
        if not self.target_material:
            return
        if len(self.slots_data) <= 1:
            QMessageBox.information(self, "Remove Slot", "A Multi-Material must have at least one slot. Cannot remove the last remaining slot.")
            return
        selected_row = self.table.currentRow()
        if selected_row < 0 or selected_row >= len(self.slots_data):
            QMessageBox.warning(self, "No Selection", "Please select a slot row to remove.")
            return

        del self.slots_data[selected_row]

        if self.chk_auto_renumber.isChecked():
            self.force_renumber_ids(refresh_table=False, sync=False)

        self.populate_table()
        new_select = min(selected_row, len(self.slots_data) - 1)
        if new_select >= 0:
            self.table.selectRow(new_select)
        if self.is_live_sync:
            self.sync_to_max("Remove Slot", update_geom=self.chk_update_faces.isChecked())
        else:
            self.set_status("● Paused: Slot removed")

    def duplicate_selected_slot(self):
        if not self.target_material:
            return
        selected_row = self.table.currentRow()
        if selected_row < 0 or selected_row >= len(self.slots_data):
            QMessageBox.warning(self, "No Selection", "Please select a slot row to duplicate.")
            return

        src_slot = self.slots_data[selected_row]
        dup_slot = dict(src_slot)

        # Clone the sub-material instance in 3ds Max
        new_sub_mat = None
        src_sub_mat = src_slot.get('sub_mat')
        if src_sub_mat is not None and rt:
            try:
                if hasattr(rt, '_jsh_MME_CloneMaterial'):
                    new_sub_mat = rt._jsh_MME_CloneMaterial(src_sub_mat)
                else:
                    new_sub_mat = rt.copy(src_sub_mat)

                if new_sub_mat is not None and str(new_sub_mat) != "undefined":
                    src_sub_name = src_slot.get('sub_mat_name', '')
                    if src_sub_name and src_sub_name not in ('(None)', 'None'):
                        try:
                            new_sub_mat.name = src_sub_name + "_Copy"
                        except Exception:
                            pass
                        dup_slot['sub_mat_name'] = str(new_sub_mat.name)
                    dup_slot['sub_mat'] = new_sub_mat
                else:
                    dup_slot['sub_mat'] = None
            except Exception as err:
                print("Error cloning sub-material: {}".format(err))
                dup_slot['sub_mat'] = None
        else:
            if src_slot.get('sub_mat_name') and src_slot.get('sub_mat_name') not in ('(None)', 'None'):
                dup_slot['sub_mat_name'] = src_slot['sub_mat_name'] + "_Copy"

        if src_slot.get('name'):
            dup_slot['name'] = src_slot['name'] + "_Copy"
        elif dup_slot.get('sub_mat_name') and dup_slot.get('sub_mat_name') not in ('(None)', 'None'):
            dup_slot['name'] = dup_slot['sub_mat_name']
        else:
            dup_slot['name'] = ""

        # The duplicated slot is a new slot with 0 faces in geometry; it must NOT claim the original slot's initial ID
        dup_slot['initial_id'] = None
        dup_slot['face_count'] = 0
        if src_slot.get('color'):
            dup_slot['color'] = QColor(src_slot['color'])

        if not self.chk_auto_renumber.isChecked():
            max_id = max([s.get('id', 0) for s in self.slots_data], default=0)
            dup_slot['id'] = max_id + 1

        self.slots_data.insert(selected_row + 1, dup_slot)

        if self.chk_auto_renumber.isChecked():
            self.force_renumber_ids(refresh_table=False, sync=False)

        self.populate_table()
        self.table.selectRow(selected_row + 1)
        if self.is_live_sync:
            self.sync_to_max("Duplicate Slot", update_geom=self.chk_update_faces.isChecked())
        else:
            self.set_status("● Paused: Slot duplicated")

    def update_button_states(self):
        has_mat = bool(self.target_material is not None and len(self.slots_data) > 0)
        can_remove = bool(self.target_material is not None and len(self.slots_data) > 1)
        if hasattr(self, 'btn_add'):
            self.btn_add.setEnabled(has_mat)
        if hasattr(self, 'btn_remove'):
            self.btn_remove.setEnabled(can_remove)
        if hasattr(self, 'btn_duplicate'):
            self.btn_duplicate.setEnabled(has_mat)

        if hasattr(self, 'chk_auto_renumber'):
            self.chk_auto_renumber.setEnabled(has_mat)
        if hasattr(self, 'chk_sync_names'):
            self.chk_sync_names.setEnabled(has_mat)
        if hasattr(self, 'chk_update_faces'):
            self.chk_update_faces.setEnabled(has_mat)

        has_geo_sel = False
        if has_mat and len(self.slots_data) > 1 and rt:
            try:
                sel_count = int(rt.selection.count)
                if sel_count > 0:
                    for obj in rt.selection:
                        if hasattr(obj, 'material') and obj.material == self.target_material:
                            has_geo_sel = True
                            break
            except Exception:
                has_geo_sel = False

        if hasattr(self, 'btn_fix_duplicates'):
            self.btn_fix_duplicates.setEnabled(has_geo_sel)
            if not has_geo_sel:
                if not has_mat or len(self.slots_data) <= 1:
                    self.btn_fix_duplicates.setToolTip("Fix Duplicates requires a Multi-Material with at least 2 slots")
                else:
                    self.btn_fix_duplicates.setToolTip("Select at least one geometry object in viewport using this material to enable Fix Duplicates")
            else:
                self.btn_fix_duplicates.setToolTip("Find duplicate sub-materials (e.g. from Attach), merge them into single slots, and remap geometry face IDs")

        # Dynamic warning on Update IDs on Geometry checkbox if material is shared across multiple scene objects
        if hasattr(self, 'chk_update_faces'):
            objs_using_mat_count = 0
            if has_mat:
                objs_list = getattr(self, '_current_scene_objs_using_mat', None)
                if objs_list is not None:
                    objs_using_mat_count = len(objs_list)
                elif rt:
                    try:
                        objs_list = self.get_objects_using_material(self.target_material)
                        self._current_scene_objs_using_mat = objs_list
                        objs_using_mat_count = len(objs_list)
                    except Exception:
                        objs_using_mat_count = 0

            if objs_using_mat_count > 1:
                self.chk_update_faces.set_warning_suffix("(slow with {} objects)".format(objs_using_mat_count))
                self.chk_update_faces.setToolTip(
                    "Warning: This Multi-Material is applied to {} objects in the scene.\n"
                    "Reassigning face Material IDs across multiple objects on every drag/reorder may cause viewport lag."
                    .format(objs_using_mat_count)
                )
            else:
                self.chk_update_faces.set_warning_suffix("")
                self.chk_update_faces.setToolTip("Reassigns face Material IDs on scene geometry to match updated slot positions")

    def find_duplicate_material_groups(self):
        """Scans self.slots_data and returns a list of duplicate groups."""
        if not self.slots_data or len(self.slots_data) < 2:
            return []

        visited = set()
        groups = []

        for i in range(len(self.slots_data)):
            if i in visited:
                continue
            slot_a = self.slots_data[i]
            sub_a = slot_a.get('sub_mat')
            if sub_a is None or str(sub_a) == "undefined":
                continue

            current_group = [i]
            for j in range(i + 1, len(self.slots_data)):
                if j in visited:
                    continue
                slot_b = self.slots_data[j]
                sub_b = slot_b.get('sub_mat')
                if sub_b is None or str(sub_b) == "undefined":
                    continue

                is_dup = False
                if rt and hasattr(rt, '_jsh_MME_AreSubMaterialsIdentical'):
                    try:
                        is_dup = bool(rt._jsh_MME_AreSubMaterialsIdentical(sub_a, sub_b))
                    except Exception:
                        is_dup = False

                if not is_dup:
                    same_class = (slot_a.get('sub_mat_class') == slot_b.get('sub_mat_class') and slot_a.get('sub_mat_class') not in ('None', None, ''))
                    same_name = (slot_a.get('sub_mat_name') == slot_b.get('sub_mat_name') and slot_a.get('sub_mat_name') not in ('None', None, ''))
                    same_color = True
                    col_a = slot_a.get('color')
                    col_b = slot_b.get('color')
                    if col_a and col_b and col_a.isValid() and col_b.isValid():
                        same_color = (col_a.rgb() == col_b.rgb())
                    is_dup = same_class and same_name and same_color

                if is_dup:
                    current_group.append(j)
                    visited.add(j)

            if len(current_group) > 1:
                visited.add(i)
                groups.append({
                    'master_idx': current_group[0],
                    'dup_indices': current_group[1:],
                    'all_indices': current_group,
                    'name': slot_a.get('sub_mat_name', slot_a.get('name', 'Material')),
                    'class': slot_a.get('sub_mat_class', ''),
                    'color': slot_a.get('color')
                })

        return groups

    def fix_duplicates(self):
        if not self.target_material or not rt:
            return

        # Collect selected objects using this material and clear sub-object mode
        selected_objs = []
        try:
            for obj in rt.selection:
                if hasattr(obj, 'material') and obj.material == self.target_material:
                    selected_objs.append(obj)
        except Exception:
            selected_objs = []

        all_objs_using_mat = self.get_objects_using_material(self.target_material)
        if not selected_objs:
            selected_objs = all_objs_using_mat

        for obj in selected_objs:
            try:
                rt._jsh_MME_ClearSubObjectSelection(obj)
            except Exception:
                pass

        groups = self.find_duplicate_material_groups()
        if not groups:
            QMessageBox.information(self, "Fix Duplicates", "No duplicate sub-materials found in the active Multi-Material.")
            return

        # 1. Visual Grouping Preview: Backup original slots_data snapshot
        self._backup_slots_data = [dict(s) for s in self.slots_data]

        # Build reordered slots_data with duplicate groups placed contiguously
        preview_slots = []
        preview_group_map = {}
        used_original_indices = set()

        for g_idx, group in enumerate(groups):
            for orig_idx in group['all_indices']:
                new_row = len(preview_slots)
                preview_slots.append(dict(self.slots_data[orig_idx]))
                preview_group_map[new_row] = g_idx
                used_original_indices.add(orig_idx)

        for idx, s in enumerate(self.slots_data):
            if idx not in used_original_indices:
                preview_slots.append(dict(s))

        self.slots_data = preview_slots
        self._preview_duplicate_groups = preview_group_map
        self.populate_table()
        self.table.viewport().update()

        # 2. Brief confirmation message
        is_shared = (len(all_objs_using_mat) > len(selected_objs))
        total_redundant = sum(len(g['dup_indices']) for g in groups)
        group_count = len(groups)
        group_str = "{} duplicate material group".format(group_count) if group_count == 1 else "{} duplicate material groups".format(group_count)
        
        dialog_text = "Found {}.\nDo you want to merge them?".format(group_str)

        reply = QMessageBox.question(
            self,
            "Fix Duplicate Sub-Materials",
            dialog_text,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )

        if reply != QMessageBox.Yes:
            # Revert preview table ordering and highlights
            self.slots_data = self._backup_slots_data
            self._preview_duplicate_groups = None
            self._backup_slots_data = None
            self.populate_table()
            self.set_status("● Fix Duplicates cancelled")
            return

        # 3. Execution: Clear preview highlights
        self._preview_duplicate_groups = None
        orig_slots = self._backup_slots_data
        self._backup_slots_data = None

        if not selected_objs:
            selected_objs = all_objs_using_mat

        rt.theHold.Begin()
        try:
            # Material Isolation: If shared with unselected objects, clone the MultiMaterial
            if is_shared:
                try:
                    if hasattr(rt, '_jsh_MME_CloneMaterial'):
                        cloned_mat = rt._jsh_MME_CloneMaterial(self.target_material)
                    else:
                        cloned_mat = rt.copy(self.target_material)
                    if cloned_mat and str(cloned_mat) != "undefined":
                        for obj in selected_objs:
                            try:
                                obj.material = cloned_mat
                            except Exception:
                                pass
                        self.target_material = cloned_mat
                except Exception as clone_err:
                    print("Error cloning MultiMaterial for isolation: {}".format(clone_err))

            # Build direct end-to-end remap map: {original_slot_id -> final_slot_id}
            dup_indices_set = set()
            for g in groups:
                for d_idx in g['dup_indices']:
                    dup_indices_set.add(d_idx)

            condensed_slots = []
            for idx, s in enumerate(orig_slots):
                if idx not in dup_indices_set:
                    condensed_slots.append(dict(s))

            auto_renumber = self.chk_auto_renumber.isChecked()
            master_orig_id_to_final_id = {}
            for new_idx, s in enumerate(condensed_slots):
                orig_id = s.get('id')
                if auto_renumber:
                    final_id = new_idx + 1
                    s['id'] = final_id
                else:
                    final_id = orig_id
                master_orig_id_to_final_id[orig_id] = final_id

            remap_map = {}
            for s in orig_slots:
                orig_id = s.get('id')
                if orig_id in master_orig_id_to_final_id:
                    remap_map[orig_id] = master_orig_id_to_final_id[orig_id]

            for g in groups:
                master_orig_slot = orig_slots[g['master_idx']]
                master_orig_id = master_orig_slot.get('id')
                final_target_id = master_orig_id_to_final_id.get(master_orig_id, master_orig_id)
                for d_idx in g['dup_indices']:
                    d_orig_slot = orig_slots[d_idx]
                    d_orig_id = d_orig_slot.get('id')
                    remap_map[d_orig_id] = final_target_id

            old_ids = list(remap_map.keys())
            new_ids = [remap_map[k] for k in old_ids]

            has_id_changes = any(o != n for o, n in zip(old_ids, new_ids))
            if has_id_changes:
                for obj in selected_objs:
                    try:
                        rt._jsh_MME_UpdateFaceIDs(obj, old_ids, new_ids)
                    except Exception as geo_err:
                        print("Error updating face IDs on {}: {}".format(getattr(obj, 'name', 'object'), geo_err))

            self.slots_data = condensed_slots
            sub_mats = [s.get('sub_mat') for s in self.slots_data]
            names = [s.get('name', '') for s in self.slots_data]
            ids = [s.get('id', i + 1) for i, s in enumerate(self.slots_data)]
            enableds = [s.get('enabled', True) for s in self.slots_data]

            rt._jsh_MME_ApplyMultiMatData(self.target_material, len(self.slots_data), sub_mats, names, ids, enableds)

            rt.theHold.Accept("Fix Duplicate Sub-Materials")

            try:
                self._last_fingerprint = str(rt._jsh_MME_GetMatFingerprint(self.target_material))
            except Exception:
                pass

            self.load_material(self.target_material)
            self.set_status("● Successfully merged {} duplicate slot(s)".format(total_redundant))

        except Exception as err:
            rt.theHold.Cancel()
            print("Error executing Fix Duplicates: {}".format(err))
            traceback.print_exc()
            QMessageBox.critical(self, "Error", "An error occurred while merging duplicates:\n{}".format(err))
            self.slots_data = orig_slots
            self.populate_table()


def show_ui(target_material=None):
    """Launches the Multi-Material Editor window."""
    global _CURRENT_JSH_MME_DIALOG
    if _CURRENT_JSH_MME_DIALOG is not None:
        try:
            _CURRENT_JSH_MME_DIALOG.close()
            _CURRENT_JSH_MME_DIALOG.deleteLater()
        except Exception:
            pass
        _CURRENT_JSH_MME_DIALOG = None

    _CURRENT_JSH_MME_DIALOG = MultiMaterialEditorUI(target_material=target_material)
    _CURRENT_JSH_MME_DIALOG.show()
    return _CURRENT_JSH_MME_DIALOG


if __name__ == "__main__":
    show_ui()
