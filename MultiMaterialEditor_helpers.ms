/*
    MultiMaterialEditor_helpers.ms
    MAXScript helper functions for MultiMaterialEditor (Python / PySide2 UI)
*/

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
        format "Error opening in SME: %\n" (getCurrentException())
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
    try (
        if subObjectLevel != 0 do subObjectLevel = 0
    ) catch()
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
    
    with undo off (
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
    )
    
    -- Unlock Windows repainting
    try ( windows.sendMessage maxHwnd 0x000B 1 0 ) catch()
    try ( completeRedraw() ) catch()
    
    count
)

fn _jsh_MME_UpdateFaceIDs obj oldIDs newIDs = (
    if obj == undefined or not isValidNode obj do return 0
    local count = 0
    
    -- Clear any active sub-object polygon/element/vertex selections
    with undo off ( _jsh_MME_ClearSubObjectSelection obj )
    
    local hasModifiers = (isProperty obj #modifiers and obj.modifiers.count > 0)
    
    if hasModifiers then (
        local topMod = obj.modifiers[1]
        local ep = if (isKindOf topMod Edit_Poly and topMod.name == "Edit Poly (Modified IDs)") then topMod else undefined
        if ep == undefined do (
            ep = Edit_Poly name:"Edit Poly (Modified IDs)"
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
            local ep = Edit_Poly name:"Edit Poly (Modified IDs)"
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
