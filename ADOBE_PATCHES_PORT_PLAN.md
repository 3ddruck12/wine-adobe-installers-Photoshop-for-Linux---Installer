# Adobe Photoshop Wine Patches - Portierungsplan für Wine 11.1

**Ziel:** Portierung der Adobe-spezifischen Patches von Wine 10.0 (Proton) nach Wine 11.1 (Vanilla)

**Status:** ✅ MACHBAR - Gutes Nachrichtsplatz: Die erforderlichen Funktionen existieren bereits in Wine 11.1!

---

## 📋 Zusammenfassung der Patches

| Patch | Priority | Komplexität | Wine 11.1 Ready? |
|-------|----------|-------------|-----------------|
| MSXML3 CDATA Wrapping | 🔴 KRITISCH | Hoch | ✅ Ja |
| MSXML3 Empty String | 🟡 MITTEL | Niedrig | ✅ Ja |
| MSHTML JavaScript Dispatch | 🔴 KRITISCH | Sehr hoch | ✅ Ja |
| MSHTML XMLSerializer | 🔴 KRITISCH | Sehr hoch | ⚠️ Partiell |

---

## 🔍 Detaillierte Analyse pro Patch

### 1️⃣ **Patch: MSXML3 CDATA Wrapping**

**Datei:** `dlls/msxml3/domdoc.c`

**Zeilen in Adobe-Wine (10.0):** 502-913 (412 neue Zeilen)  
**Zeilen in Vanilla Wine (11.1):** 489 (doparse Funktion)

#### ✅ Status: **SOFORT PORTIERBAR**

**Grund:** 
- Die `doparse()` Funktion existiert an der gleichen Position (Zeile ~489)
- Alle benötigten Helper-Funktionen (`xmlCharEncoding`, `libxml2` APIs) sind vorhanden
- Keine Abhängigkeiten von Proton-spezifischem Code

**Schritte:**
1. Kopiere die neuen Helper-Funktionen (Zeilen 502-658 aus Adobe-Wine):
   - `is_xml_decl()`
   - `is_whitespace()`
   - `is_start_tag()`
   - `is_pi()`
   - `is_markup_decl()`
   - `is_gt()`
   - `is_self_close()`
   - `wrap_embedded_xml_in_cdata()`

2. Integriere die Wrapper-Logik in `doparse()` (um Zeile 489 in Wine 11.1)

3. Füge `free(modified_ptr)` an den Cleanup-Stellen ein

**Geschätzter Aufwand:** 🟢 **30 Minuten**

---

### 2️⃣ **Patch: MSXML3 Empty String Handling**

**Datei:** `dlls/msxml3/domdoc.c`

**Zeilen in Adobe-Wine (10.0):** ~2901-2902  
**Zeilen in Vanilla Wine (11.1):** ~2500 (Schätzung, `loadXML()` Funktion)

#### ✅ Status: **TRIVIAL PORTIERBAR**

**Änderung:** Nur 2 Zeilen Code
```c
// VOR (fehlerhaft):
xmldoc = doparse(This, (char*)ptr, lstrlenW(ptr)*sizeof(WCHAR), XML_CHAR_ENCODING_UTF16LE);

// NACH (Phials fix):
if (*ptr)
    xmldoc = doparse(This, (char*)ptr, lstrlenW(ptr)*sizeof(WCHAR), XML_CHAR_ENCODING_UTF16LE);
```

**Geschätzter Aufwand:** 🟢 **5 Minuten**

---

### 3️⃣ **Patch: MSHTML JavaScript Dispatch Fix**

**Dateien:**
- `dlls/mshtml/dispex.c`
- `dlls/mshtml/htmlelem.c`
- `dlls/mshtml/htmlevent.c`
- `dlls/mshtml/htmlevent.h`
- `dlls/mshtml/htmlnode.c`

#### ✅ Status: **PORTIERBAR mit minimalen Anpassungen**

**Gute Nachrichten:**
- `is_dynamic_dispid()` existiert bereits in Wine 11.1 (Zeile 693)
- Die Event-Handler-Struktur ist gleich
- `DispatchEx` Architektur ist identisch

**Änderungen pro Datei:**

##### `dispex.c`
- **Zeile:** ~2321 in Adobe-Wine → ~2318-2320 in Wine 11.1
- **Änderung:** `if(This->jsdisp)` → `if(This->jsdisp && !is_dynamic_dispid(id))`
- **Grund:** Verhindert dass Adobe's JSObject-Properties an jscript delegiert werden

**Geschätzter Aufwand:** 🟢 **5 Minuten**

##### `htmlelem.c`
- **Zeile:** ~1171-1180 in Adobe-Wine (neue Funktion)
- **Ziel:** Intercepte Event-Handler-Attribute (`onclick`, `onload` etc.)
- **Komplexität:** Mittel (muss vorhandene `setAttribute()` Funktion anpassen)

**Pseudo-Code:**
```c
// In HTMLElement_setAttribute()
if (compat_mode >= COMPAT_MODE_IE9 && This->dom_element &&
    strAttributeName[0] && (strAttributeName[0] == 'o' || strAttributeName[0] == 'O') &&
    strAttributeName[1] && (strAttributeName[1] == 'n' || strAttributeName[1] == 'N')) {
    
    hres = set_node_event_handler_by_attr(&This->node, strAttributeName, &val);
    if(SUCCEEDED(hres))
        goto done;  // Springe zum Ende der Funktion
    // Fallback: Normales Attribute-Handling
}
```

**Geschätzter Aufwand:** 🟡 **30 Minuten**

##### `htmlevent.c` & `htmlevent.h`
- **Zeile:** ~4749-4800 in Adobe-Wine
- **Änderung:** Rewrite des Event-String-Handlers
- **Ziel:** Compile string event handlers (`element.onclick="code"`) statt sie nur zu speichern
- **Neue Funktion:** `set_node_event_handler_by_attr()`

**Pseudo-Code:**
```c
HRESULT set_node_event_handler_by_attr(HTMLDOMNode *node, const WCHAR *attr_name, VARIANT *var) {
    eventid_t eid = attr_to_eid(attr_name);
    if (eid == EVENTID_LAST)
        return DISP_E_UNKNOWNNAME;
    
    // Wenn es ein String ist, compile ihn
    if (V_VT(var) == VT_BSTR) {
        HTMLInnerWindow *script_global = get_script_global(&event_target->dispex);
        if (script_global) {
            IDispatch *disp = script_parse_event(script_global, V_BSTR(var));
            // ... dann setze disp statt String
        }
    }
    return set_node_event(node, eid, var);
}
```

**Geschätzter Aufwand:** 🟡 **45 Minuten**

##### `htmlnode.c`
- **Änderung:** `NodeList_dispex` - entferne `init_info` (verhindert JSObject-Property)
- **Impact:** Minimal

**Geschätzter Aufwand:** 🟢 **5 Minuten**

---

### 4️⃣ **Patch: IXMLSerializer Implementierung**

**Dateien:**
- `dlls/mshtml/omnavigator.c` (+174 Zeilen)
- `dlls/mshtml/mshtml_private.h`
- `include/mshtml.idl`
- `include/mshtmdid.h`

#### ⚠️ Status: **MACHBAR aber KOMPLEX**

**Problem:** 
- Proton/Valve Wine hat eine andere HTML/DOM-Architektur als Vanilla Wine 11.1
- Die Struktur von `omnavigator.c` könnte unterschiedlich sein

**Lösung:**
1. **Prüfe:** Existiert `IXMLSerializer` bereits in Wine 11.1?
   ```bash
   grep -r "IXMLSerializer" /path/to/wine-11.1/include/
   ```

2. **Falls nicht:** Implementierung notwendig
   - Strukturen in `omnavigator.c` hinzufügen
   - `serializeToString()` Methode implementieren (XML-Serialisierung)
   - Verzeichnis-Integration in `mshtml_private.h`

3. **Falls ja:** Prüfe ob es vollständig ist
   - Wenn nicht: Ergänze fehlende Methoden

**Geschätzter Aufwand:** 🟠 **60-90 Minuten** (abhängig von vorhandenem Code)

---

## 🎯 Prioritäts-Reihenfolge (empfohlen)

### Phase 1: Kritische Fixes (für Installer zu funktionieren) ⏱️ **~2 Stunden**

1. **MSXML3 CDATA Wrapping** ← Ermöglicht PS2021/PS2025 Installer XML-Parsing
   - Behebt E103 Fehler bei ~30% Installation
   
2. **IXMLSerializer** ← Ermöglicht Dropdown-Wert-Übermittlung
   - Kritisch für Installer UI

3. **MSHTML JavaScript Dispatch** ← Stabilisiert Event-Handling
   - Verhindert Crashes bei UI-Interaktion

### Phase 2: Optimierungen (Stabilität verbessern) ⏱️ **~1 Stunde**

4. **MSXML3 Empty String Handling** ← Verhindert Logspam
5. **Event-Handler String-Compilation** ← Ermöglicht dynamische Event-Handler

---

## 📝 Schritt-für-Schritt Implementierungs-Plan

### Schritt 1: Vorbereitung
```bash
cd /path/to/wine-11.1

# Backup erstellen
cp -r dlls/msxml3/domdoc.c dlls/msxml3/domdoc.c.bak
cp -r dlls/mshtml/dispex.c dlls/mshtml/dispex.c.bak
# ... weitere Backups

# Branch erstellen
git checkout -b adobe-photoshop-patches
```

### Schritt 2: MSXML3 CDATA Wrapping (30 Min)
1. Öffne: `dlls/msxml3/domdoc.c`
2. Suche nach: `static xmlDocPtr doparse()`
3. Füge Helper-Funktionen VOR `doparse()` ein
4. Modifiziere `doparse()` um `wrap_embedded_xml_in_cdata()` zu nutzen

### Schritt 3: MSHTML Dispex Fix (5 Min)
1. Öffne: `dlls/mshtml/dispex.c`
2. Suche nach: `if(This->jsdisp)` (um Zeile 2318)
3. Ändere zu: `if(This->jsdisp && !is_dynamic_dispid(id))`

### Schritt 4: HTMLElement setAttribute Interception (30 Min)
1. Öffne: `dlls/mshtml/htmlelem.c`
2. Suche nach: `static HRESULT WINAPI HTMLElement_setAttribute()`
3. Füge Event-Handler Interception VOR dem normalen setAttribute-Code hinzu

### Schritt 5: Event-Handler String Compilation (45 Min)
1. Öffne: `dlls/mshtml/htmlevent.c`
2. Suche nach: `case VT_BSTR:` im `set_event_handler()`
3. Ersetze mit Compiler-Logik statt nur Storage

### Schritt 6: IXMLSerializer (60-90 Min)
1. Prüfe ob `IXMLSerializer` existiert in `include/mshtml.idl`
2. Falls nicht: Füge Definition hinzu
3. Implementiere in `dlls/mshtml/omnavigator.c`
4. Registriere in `mshtml_private.h`

### Schritt 7: Testen
```bash
# Rebuild
./configure
make -j4

# Test mit Adobe Installer
```

---

## ⚠️ Potenzielle Probleme & Lösungen

| Problem | Symptom | Lösung |
|---------|---------|--------|
| **Funktion nicht gefunden** | Compile-Error | Prüfe Wine 11.1 Quellcode, adaptiere Namen |
| **API Unterschiede** | Runtime-Error | Wrapper-Funktionen schreiben |
| **Struct Layout anders** | Segfault | Vergleiche mit Wine 11.1 Header-Dateien |
| **Abhängigkeits-Chain** | Unerwartete Fehler | Testen mit & ohne alle 5 Patches |

---

## 📊 Aufwands-Schätzung

| Phase | Aufwand | Risiko |
|-------|---------|--------|
| MSXML3 Patches (1+2) | **35 Min** | 🟢 Niedrig |
| MSHTML Dispex Fix | **5 Min** | 🟢 Niedrig |
| Event Handling (htmlevent) | **45 Min** | 🟡 Mittel |
| HTMLElement setAttribute | **30 Min** | 🟡 Mittel |
| HTMLNode Fix | **5 Min** | 🟢 Niedrig |
| IXMLSerializer | **60-90 Min** | 🔴 Hoch |
| Testing & Debugging | **60-120 Min** | 🔴 Hoch |
| **TOTAL** | **~4-5 Stunden** | 🟡 |

---

## ✅ Erfolgs-Kriterien

Nach der Portierung sollten folgende Ziele erreicht sein:

- ✅ Adobe Photoshop CC 2021 Installer startet
- ✅ Installation läuft bis mindestens 50% (ohne Crashes bei 30%)
- ✅ Dropdown-Felder funktionieren (Sprache, Installationsort)
- ✅ Keine E103 XML-Parser Fehler
- ✅ Keine kritischen JavaScript-Fehler
- ✅ Log ist sauber (keine FIXME/ERR beim Installer)

---

## 🔗 Referenzen

**Original Adobe-Wine Patches:**
- Commit: `59250d93828036b255e0f092e9fd0d35e8ded3aa` (MSXML3 CDATA)
- Commit: `96cddf74a2d3dce46468fde030868b2417ffec13` (MSXML3 Empty String)
- Commit: `bfabbea80c534daf94f83652a6fc3e0eb51e7b08` (MSHTML JavaScript)
- Commit: `984d780528034605a859512be35446788d3e2b5f` (IXMLSerializer)

**Source:** https://github.com/PhialsBasement/wine-adobe-installers

---

## 📌 Nächste Schritte

1. **SOFORT:** Starte mit Phase 1 (MSXML3 + dispex + IXMLSerializer)
2. **PARALLEL:** Teste nach jedem Schritt
3. **DOKUMENTATION:** Committe mit aussagekräftigen Nachrichten
4. **INTEGRATION:** Merge in main branch nach erfolgreichem Testing
