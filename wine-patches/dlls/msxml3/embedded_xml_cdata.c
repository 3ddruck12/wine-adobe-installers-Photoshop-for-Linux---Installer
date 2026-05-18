/*
 * Wrap embedded XML declarations in CDATA for Adobe installer compatibility.
 *
 * Windows MSXML tolerates embedded <?xml?> declarations but libxml2/SAX does not.
 *
 * Copyright (C) 2026  (3ddruck12)
 * SPDX-License-Identifier: LGPL-2.1-or-later
 */

#include <stdarg.h>
#include <string.h>

#include <libxml/parser.h>

#define COBJMACROS

#include "windef.h"
#include "winbase.h"
#include "ole2.h"
#include "msxml6.h"

#include "wine/debug.h"

#include "msxml_private.h"
#include "embedded_xml_cdata.h"

WINE_DEFAULT_DEBUG_CHANNEL(msxml);

/* Check if ptr points to "<?xml" in UTF-8 or UTF-16LE format */
static int is_xml_decl(const char *ptr, int len, int is_utf16)
{
    if (is_utf16)
    {
        if (len < 10) return 0;
        return ptr[0] == '<' && ptr[1] == 0 &&
               ptr[2] == '?' && ptr[3] == 0 &&
               ptr[4] == 'x' && ptr[5] == 0 &&
               ptr[6] == 'm' && ptr[7] == 0 &&
               ptr[8] == 'l' && ptr[9] == 0;
    }
    if (len < 5) return 0;
    return !strncmp(ptr, "<?xml", 5);
}

static int is_ws(const char *ptr, int is_utf16)
{
    char c = ptr[0];
    if (is_utf16 && ptr[1] != 0) return 0;
    return c == ' ' || c == '\t' || c == '\r' || c == '\n';
}

static int is_close_tag(const char *ptr, int len, int is_utf16)
{
    if (is_utf16)
    {
        if (len < 4) return 0;
        return ptr[0] == '<' && ptr[1] == 0 && ptr[2] == '/' && ptr[3] == 0;
    }
    if (len < 2) return 0;
    return ptr[0] == '<' && ptr[1] == '/';
}

static int is_start_tag(const char *ptr, int len, int is_utf16)
{
    char c;
    if (is_utf16)
    {
        if (len < 4) return 0;
        if (ptr[0] != '<' || ptr[1] != 0) return 0;
        c = ptr[2];
        if (ptr[3] != 0) return 0;
    }
    else
    {
        if (len < 2) return 0;
        if (ptr[0] != '<') return 0;
        c = ptr[1];
    }
    return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z');
}

static int is_gt(const char *ptr, int is_utf16)
{
    if (is_utf16)
        return ptr[0] == '>' && ptr[1] == 0;
    return ptr[0] == '>';
}

static int is_self_close(const char *ptr, int len, int is_utf16)
{
    if (is_utf16)
    {
        if (len < 4) return 0;
        return ptr[0] == '/' && ptr[1] == 0 && ptr[2] == '>' && ptr[3] == 0;
    }
    if (len < 2) return 0;
    return ptr[0] == '/' && ptr[1] == '>';
}

static int is_markup_decl(const char *ptr, int len, int is_utf16)
{
    if (is_utf16)
    {
        if (len < 4) return 0;
        return ptr[0] == '<' && ptr[1] == 0 && ptr[2] == '!' && ptr[3] == 0;
    }
    if (len < 2) return 0;
    return ptr[0] == '<' && ptr[1] == '!';
}

static int is_pi(const char *ptr, int len, int is_utf16)
{
    if (is_utf16)
    {
        if (len < 4) return 0;
        return ptr[0] == '<' && ptr[1] == 0 && ptr[2] == '?' && ptr[3] == 0;
    }
    if (len < 2) return 0;
    return ptr[0] == '<' && ptr[1] == '?';
}

static int is_xmldata_element(const char *ptr, int len, int is_utf16)
{
    const char *p = ptr;
    const char *end = ptr + len;
    const char *name_end = NULL;
    int char_size = is_utf16 ? 2 : 1;
    const char *suffix_check;

    while (p + char_size <= end)
    {
        char c = p[0];
        if (is_utf16 && p[1] != 0) { p += char_size; continue; }
        if (c == ' ' || c == '\t' || c == '\r' || c == '\n' || c == '>' || c == '/')
        {
            name_end = p;
            break;
        }
        p += char_size;
    }
    if (!name_end) return 0;

    if ((name_end - ptr) / char_size < 7) return 0;

    suffix_check = name_end - (7 * char_size);
    if (is_utf16)
    {
        return suffix_check[0] == 'X' && suffix_check[1] == 0 &&
               suffix_check[2] == 'M' && suffix_check[3] == 0 &&
               suffix_check[4] == 'L' && suffix_check[5] == 0 &&
               suffix_check[6] == 'D' && suffix_check[7] == 0 &&
               suffix_check[8] == 'a' && suffix_check[9] == 0 &&
               suffix_check[10] == 't' && suffix_check[11] == 0 &&
               suffix_check[12] == 'a' && suffix_check[13] == 0;
    }
    return !strncmp(suffix_check, "XMLData", 7);
}

static char *wrap_embedded_xml_in_cdata(const char *ptr, int len, int *new_len, xmlCharEncoding encoding)
{
    const char *p, *decl_start, *content_start, *content_end = NULL, *end;
    char *result, *dst;
    int skip_first = 0;
    int is_utf16 = (encoding == XML_CHAR_ENCODING_UTF16LE);
    int char_size = is_utf16 ? 2 : 1;
    int decl_size = is_utf16 ? 10 : 5;
    int nesting;

    TRACE("len=%d encoding=%d is_utf16=%d\n", len, encoding, is_utf16);

    end = ptr + len;

    p = ptr;
    while (p + char_size <= end && is_ws(p, is_utf16))
        p += char_size;
    if (p + decl_size <= end && is_xml_decl(p, end - p, is_utf16))
        skip_first = 1;

    decl_start = NULL;
    for (p = ptr; p + decl_size <= end; p += char_size)
    {
        if (is_xml_decl(p, end - p, is_utf16))
        {
            if (skip_first)
            {
                skip_first = 0;
                continue;
            }
            decl_start = p;
            break;
        }
    }

    if (!decl_start)
    {
        const char *xmldata_start = NULL;
        const char *xmldata_content = NULL;

        for (p = ptr; p + char_size <= end; p += char_size)
        {
            if (is_start_tag(p, end - p, is_utf16))
            {
                if (is_xmldata_element(p + char_size, end - p - char_size, is_utf16))
                {
                    const char *tag_end;
                    for (tag_end = p + char_size; tag_end + char_size <= end; tag_end += char_size)
                    {
                        if (is_gt(tag_end, is_utf16))
                        {
                            xmldata_content = tag_end + char_size;
                            break;
                        }
                        if (is_self_close(tag_end, end - tag_end, is_utf16))
                            break;
                    }
                    if (xmldata_content)
                    {
                        const char *content_check = xmldata_content;
                        while (content_check + char_size <= end && is_ws(content_check, is_utf16))
                            content_check += char_size;
                        if (is_start_tag(content_check, end - content_check, is_utf16) &&
                            !is_pi(content_check, end - content_check, is_utf16) &&
                            !is_markup_decl(content_check, end - content_check, is_utf16))
                        {
                            xmldata_start = p;
                            content_start = xmldata_content;
                            TRACE("found *XMLData element with element content\n");
                            break;
                        }
                    }
                }
            }
        }

        if (!xmldata_start)
        {
            TRACE("no embedded declarations found\n");
            return NULL;
        }

        nesting = 0;
        for (p = content_start; p + char_size <= end; p += char_size)
        {
            if (is_start_tag(p, end - p, is_utf16))
            {
                const char *tag_end;
                int is_selfclose = 0;
                for (tag_end = p + char_size; tag_end + char_size <= end; tag_end += char_size)
                {
                    if (is_self_close(tag_end, end - tag_end, is_utf16))
                    {
                        is_selfclose = 1;
                        break;
                    }
                    if (is_gt(tag_end, is_utf16))
                        break;
                }
                if (!is_selfclose)
                    nesting++;
            }
            else if (is_close_tag(p, end - p, is_utf16))
            {
                if (nesting == 0)
                {
                    content_end = p;
                    break;
                }
                nesting--;
            }
        }
        if (!content_end)
        {
            TRACE("could not find *XMLData element end\n");
            return NULL;
        }
        goto do_wrap;
    }

    content_start = NULL;
    for (p = decl_start - char_size; p >= ptr; p -= char_size)
    {
        if (is_gt(p, is_utf16))
        {
            content_start = p + char_size;
            break;
        }
    }
    if (!content_start)
    {
        TRACE("could not find parent element start\n");
        return NULL;
    }

    nesting = 0;
    content_end = NULL;
    for (p = decl_start; p + char_size <= end; p += char_size)
    {
        if (is_start_tag(p, end - p, is_utf16))
        {
            const char *tag_end;
            int is_selfclose = 0;
            for (tag_end = p + char_size; tag_end + char_size <= end; tag_end += char_size)
            {
                if (is_self_close(tag_end, end - tag_end, is_utf16))
                {
                    is_selfclose = 1;
                    break;
                }
                if (is_gt(tag_end, is_utf16))
                    break;
            }
            if (!is_selfclose)
                nesting++;
        }
        else if (is_close_tag(p, end - p, is_utf16))
        {
            if (nesting == 0)
            {
                content_end = p;
                break;
            }
            nesting--;
        }
    }
    if (!content_end)
    {
        TRACE("could not find parent element end\n");
        return NULL;
    }

do_wrap:
    TRACE("wrapping content in CDATA: start=%d end=%d\n",
          (int)(content_start - ptr), (int)(content_end - ptr));

    result = malloc(len + 24 * char_size + char_size);
    if (!result)
        return NULL;

    dst = result;
    for (p = ptr; p < content_start; p++)
        *dst++ = *p;
    if (is_utf16)
    {
        *dst++ = '<'; *dst++ = 0;
        *dst++ = '!'; *dst++ = 0;
        *dst++ = '['; *dst++ = 0;
        *dst++ = 'C'; *dst++ = 0;
        *dst++ = 'D'; *dst++ = 0;
        *dst++ = 'A'; *dst++ = 0;
        *dst++ = 'T'; *dst++ = 0;
        *dst++ = 'A'; *dst++ = 0;
        *dst++ = '['; *dst++ = 0;
    }
    else
    {
        memcpy(dst, "<![CDATA[", 9);
        dst += 9;
    }
    for (p = content_start; p < content_end; p++)
        *dst++ = *p;
    if (is_utf16)
    {
        *dst++ = ']'; *dst++ = 0;
        *dst++ = ']'; *dst++ = 0;
        *dst++ = '>'; *dst++ = 0;
    }
    else
    {
        memcpy(dst, "]]>", 3);
        dst += 3;
    }
    for (p = content_end; p < end; p++)
        *dst++ = *p;

    if (is_utf16)
        *dst++ = 0;
    *dst = '\0';
    *new_len = dst - result - (is_utf16 ? 1 : 0);
    return result;
}

static HRESULT stream_read_all(ISequentialStream *stream, char **data, DWORD *size)
{
    DWORD total = 0, capacity = 8192, read;
    char *buf;
    HRESULT hr;

    if (!(buf = malloc(capacity)))
        return E_OUTOFMEMORY;

    for (;;)
    {
        if (total + 4096 > capacity)
        {
            char *tmp;
            capacity *= 2;
            if (!(tmp = realloc(buf, capacity)))
            {
                free(buf);
                return E_OUTOFMEMORY;
            }
            buf = tmp;
        }
        hr = ISequentialStream_Read(stream, buf + total, capacity - total, &read);
        if (FAILED(hr))
        {
            free(buf);
            return hr;
        }
        if (read == 0)
            break;
        total += read;
    }

    *data = buf;
    *size = total;
    return S_OK;
}

HRESULT embedded_xml_preprocess_stream(ISequentialStream *stream, bool utf16,
        ISequentialStream **out_stream, void **owned_buffer)
{
    char *data, *modified;
    DWORD size;
    int new_len;
    HRESULT hr;
    xmlCharEncoding encoding = utf16 ? XML_CHAR_ENCODING_UTF16LE : XML_CHAR_ENCODING_UTF8;

    *out_stream = NULL;
    *owned_buffer = NULL;

    if (FAILED(hr = stream_read_all(stream, &data, &size)))
        return hr;

    modified = wrap_embedded_xml_in_cdata(data, size, &new_len, encoding);
    free(data);
    if (!modified)
        return S_OK;

    hr = stream_wrapper_create(modified, new_len, out_stream);
    if (FAILED(hr))
    {
        free(modified);
        return hr;
    }

    *owned_buffer = modified;
    return S_OK;
}
