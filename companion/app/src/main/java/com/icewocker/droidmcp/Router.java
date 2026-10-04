package com.icewocker.droidmcp;

import android.content.Context;

import java.io.UnsupportedEncodingException;
import java.net.URLDecoder;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;

import org.json.JSONException;
import org.json.JSONObject;

/**
 * 路由：拆 path/query、校验 token、分发到 Api、统一 envelop。
 *
 * envelop（严格按协议）：
 * 成功 {"ok": true, "data": ...} / 失败 {"ok": false, "error": "..."}，
 * error 取值 no_token / denied / bad_args / unavailable。
 *
 * 鉴权：query ?token= 或头 Authorization: Bearer，错了回 no_token。
 * 全部端点（含 /api/ping）统一要求 token。
 */
public final class Router {

    private Router() {
    }

    /** HTTP 状态码 + JSON 串。 */
    public static final class Response {
        public final int status;
        public final String json;

        public Response(int status, String json) {
            this.status = status;
            this.json = json;
        }
    }

    public static Response ok(Object data) {
        return new Response(200, okJson(data));
    }

    public static Response err(String code) {
        return err(code, null);
    }

    public static Response err(String code, Object data) {
        int status = 400;
        if ("no_token".equals(code)) {
            status = 401;
        } else if ("denied".equals(code)) {
            status = 403;
        } else if ("unavailable".equals(code)) {
            status = 500;
        }
        return new Response(status, errJson(code, data));
    }

    public static Response badArgs(String msg) {
        return err("bad_args", msg);
    }

    public static Response denied(String where) {
        return err("denied", where);
    }

    public static Response unavailable(String msg) {
        return err("unavailable", msg);
    }

    static String okJson(Object data) {
        try {
            JSONObject o = new JSONObject();
            o.put("ok", true);
            o.put("data", data == null ? JSONObject.NULL : data);
            return o.toString();
        } catch (JSONException e) {
            return "{\"ok\":true}";
        }
    }

    static String errJson(String code, Object data) {
        try {
            JSONObject o = new JSONObject();
            o.put("ok", false);
            o.put("error", code);
            if (data != null) {
                o.put("data", data);
            }
            return o.toString();
        } catch (JSONException e) {
            return "{\"ok\":false,\"error\":\"" + code + "\"}";
        }
    }

    /** 纯 Java query 解析（无 Android 依赖，可单元测试）。 */
    public static Map<String, String> parseQuery(String raw) {
        Map<String, String> out = new LinkedHashMap<String, String>();
        if (raw == null || raw.isEmpty()) {
            return out;
        }
        String[] pairs = raw.split("&");
        for (int i = 0; i < pairs.length; i++) {
            String p = pairs[i];
            if (p.isEmpty()) {
                continue;
            }
            int eq = p.indexOf('=');
            String k = eq < 0 ? p : p.substring(0, eq);
            String v = eq < 0 ? "" : p.substring(eq + 1);
            out.put(decode(k), decode(v));
        }
        return out;
    }

    private static String decode(String s) {
        try {
            return URLDecoder.decode(s, "UTF-8");
        } catch (UnsupportedEncodingException e) {
            return s;
        }
    }

    /**
     * @param method  大写 HTTP 方法（GET/POST）
     * @param target  请求行里的 origin-form（/api/xxx?a=b）
     * @param headers 已小写 key 的头
     * @param body    POST JSON body（无则为空 JSONObject）
     */
    public static Response route(Context ctx, String method, String target,
                                 Map<String, String> headers, JSONObject body) {
        if (method == null || target == null) {
            return badArgs("请求行非法");
        }
        method = method.toUpperCase(Locale.US);
        String path = target;
        Map<String, String> query = new LinkedHashMap<String, String>();
        int q = target.indexOf('?');
        if (q >= 0) {
            path = target.substring(0, q);
            query = parseQuery(target.substring(q + 1));
        }
        if (body == null) {
            body = new JSONObject();
        }

        String token = query.get("token");
        if (token == null || token.isEmpty()) {
            String auth = headers.get("authorization");
            if (auth != null && auth.length() > 7
                    && auth.regionMatches(true, 0, "Bearer ", 0, 7)) {
                token = auth.substring(7).trim();
            }
        }
        if (token == null || !token.equals(Store.getToken(ctx))) {
            return err("no_token");
        }

        return Api.dispatch(ctx, method, path, query, body);
    }
}
