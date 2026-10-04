package com.icewocker.droidmcp;

import android.content.Context;
import android.content.SharedPreferences;

import java.security.SecureRandom;

/**
 * SharedPreferences 存取：token（首次生成 16 位）与短信/拨号开关。
 *
 * 开关默认全部关闭，对应协议安全边界第 3 条：
 * 发短信/拨号是真金白银的操作，需用户在 App 内手动打开。
 */
public final class Store {

    private static final String PREFS = "droid_mcp";
    private static final String KEY_TOKEN = "token";
    private static final String KEY_SMS_ALLOWED = "sms_allowed";
    private static final String KEY_DIAL_ALLOWED = "dial_allowed";

    private static final int TOKEN_LEN = 16;
    private static final String ALPHABET =
            "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789";

    private Store() {
    }

    private static SharedPreferences prefs(Context ctx) {
        return ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    /** 取 token，不存在则生成并持久化。 */
    public static synchronized String getToken(Context ctx) {
        String t = prefs(ctx).getString(KEY_TOKEN, null);
        if (t == null || t.length() != TOKEN_LEN) {
            t = newToken();
            prefs(ctx).edit().putString(KEY_TOKEN, t).apply();
        }
        return t;
    }

    static String newToken() {
        SecureRandom r = new SecureRandom();
        StringBuilder sb = new StringBuilder(TOKEN_LEN);
        for (int i = 0; i < TOKEN_LEN; i++) {
            sb.append(ALPHABET.charAt(r.nextInt(ALPHABET.length())));
        }
        return sb.toString();
    }

    public static boolean isSmsAllowed(Context ctx) {
        return prefs(ctx).getBoolean(KEY_SMS_ALLOWED, false);
    }

    public static void setSmsAllowed(Context ctx, boolean v) {
        prefs(ctx).edit().putBoolean(KEY_SMS_ALLOWED, v).apply();
    }

    public static boolean isDialAllowed(Context ctx) {
        return prefs(ctx).getBoolean(KEY_DIAL_ALLOWED, false);
    }

    public static void setDialAllowed(Context ctx, boolean v) {
        prefs(ctx).edit().putBoolean(KEY_DIAL_ALLOWED, v).apply();
    }
}
