/*
 * Adobe installer: wrap embedded XML in CDATA (MSXML compatibility).
 *
 * Copyright (C) 2026  (3ddruck12)
 * SPDX-License-Identifier: LGPL-2.1-or-later
 */

#ifndef __EMBEDDED_XML_CDATA__
#define __EMBEDDED_XML_CDATA__

#include "objidl.h"

HRESULT embedded_xml_preprocess_stream(ISequentialStream *stream, bool utf16,
        ISequentialStream **out_stream, void **owned_buffer);

#endif
