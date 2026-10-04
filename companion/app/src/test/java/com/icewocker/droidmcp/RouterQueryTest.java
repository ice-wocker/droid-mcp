package com.icewocker.droidmcp;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

import java.util.Map;

/** Router.parseQuery 是纯 Java，可在本地 JVM 单测。 */
public class RouterQueryTest {

    @Test
    public void parseSimple() {
        Map<String, String> q = Router.parseQuery("token=abc&limit=20");
        assertEquals("abc", q.get("token"));
        assertEquals("20", q.get("limit"));
    }

    @Test
    public void parseEmpty() {
        assertTrue(Router.parseQuery("").isEmpty());
        assertTrue(Router.parseQuery(null).isEmpty());
    }

    @Test
    public void parseUrlEncoding() {
        Map<String, String> q = Router.parseQuery("path=%2Fsdcard%2FDownload&flag");
        assertEquals("/sdcard/Download", q.get("path"));
        assertEquals("", q.get("flag"));
    }
}
