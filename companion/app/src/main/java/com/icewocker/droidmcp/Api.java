package com.icewocker.droidmcp;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.ContentResolver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.location.Location;
import android.location.LocationManager;
import android.net.Uri;
import android.net.wifi.WifiInfo;
import android.net.wifi.WifiManager;
import android.os.BatteryManager;
import android.os.Build;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.provider.CallLog;
import android.provider.ContactsContract;
import android.provider.Telephony;
import android.telephony.SmsManager;
import android.widget.Toast;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

/**
 * 协议 v1 全部 20 个端点（与 MCP 工具名一一对应）。
 *
 * 无权限时 error=denied 且 data 写去手机哪里开；
 * sms/send 与 call/dial 先查 Store 开关，关着就 denied；
 * storage 默认只给 Download 与 App 外部目录，超出报 denied 并提示去开所有文件访问权限；
 * apps 用 PackageManager 列出，去掉无启动图标的系统项。
 */
public final class Api {

    private static final String VERSION = "0.2.0";
    private static final String NAME = "droid-mcp-companion";
    private static final String NOTIFY_CHANNEL = "droid-mcp";

    private Api() {
    }

    public static Router.Response dispatch(Context ctx, String method, String path,
                                            Map<String, String> query, JSONObject body) {
        try {
            // 先判方法再执行业务：写操作（POST）绝不能在方法不匹配时产生副作用。
            if ("/api/ping".equals(path)) {
                if (!"GET".equals(method)) {
                    return Router.badArgs("该端点只支持 GET");
                }
                return ping();
            } else if ("/api/device/info".equals(path)) {
                if (!"GET".equals(method)) {
                    return Router.badArgs("该端点只支持 GET");
                }
                return deviceInfo(ctx);
            } else if ("/api/battery".equals(path)) {
                if (!"GET".equals(method)) {
                    return Router.badArgs("该端点只支持 GET");
                }
                return battery(ctx);
            } else if ("/api/sms/inbox".equals(path)) {
                if (!"GET".equals(method)) {
                    return Router.badArgs("该端点只支持 GET");
                }
                return smsInbox(ctx, query);
            } else if ("/api/sms/send".equals(path)) {
                if (!"POST".equals(method)) {
                    return Router.badArgs("该端点只支持 POST（JSON body）");
                }
                return smsSend(ctx, query, body);
            } else if ("/api/call/log".equals(path)) {
                if (!"GET".equals(method)) {
                    return Router.badArgs("该端点只支持 GET");
                }
                return callLog(ctx, query);
            } else if ("/api/call/dial".equals(path)) {
                if (!"POST".equals(method)) {
                    return Router.badArgs("该端点只支持 POST（JSON body）");
                }
                return callDial(ctx, query, body);
            } else if ("/api/contacts".equals(path)) {
                if (!"GET".equals(method)) {
                    return Router.badArgs("该端点只支持 GET");
                }
                return contacts(ctx);
            } else if ("/api/clipboard/get".equals(path)) {
                if (!"GET".equals(method)) {
                    return Router.badArgs("该端点只支持 GET");
                }
                return clipboardGet(ctx);
            } else if ("/api/clipboard/set".equals(path)) {
                if (!"POST".equals(method)) {
                    return Router.badArgs("该端点只支持 POST（JSON body）");
                }
                return clipboardSet(ctx, query, body);
            } else if ("/api/notify".equals(path)) {
                if (!"POST".equals(method)) {
                    return Router.badArgs("该端点只支持 POST（JSON body）");
                }
                return notify(ctx, query, body);
            } else if ("/api/notification/remove".equals(path)) {
                if (!"POST".equals(method)) {
                    return Router.badArgs("该端点只支持 POST（JSON body）");
                }
                return notificationRemove(ctx, query, body);
            } else if ("/api/toast".equals(path)) {
                if (!"POST".equals(method)) {
                    return Router.badArgs("该端点只支持 POST（JSON body）");
                }
                return toast(ctx, query, body);
            } else if ("/api/vibrate".equals(path)) {
                if (!"POST".equals(method)) {
                    return Router.badArgs("该端点只支持 POST（JSON body）");
                }
                return vibrate(ctx, query, body);
            } else if ("/api/wifi".equals(path)) {
                if (!"GET".equals(method)) {
                    return Router.badArgs("该端点只支持 GET");
                }
                return wifi(ctx);
            } else if ("/api/location".equals(path)) {
                if (!"GET".equals(method)) {
                    return Router.badArgs("该端点只支持 GET");
                }
                return location(ctx, query);
            } else if ("/api/storage/list".equals(path)) {
                if (!"GET".equals(method)) {
                    return Router.badArgs("该端点只支持 GET");
                }
                return storageList(ctx, query);
            } else if ("/api/storage/read".equals(path)) {
                if (!"GET".equals(method)) {
                    return Router.badArgs("该端点只支持 GET");
                }
                return storageRead(ctx, query);
            } else if ("/api/storage/write".equals(path)) {
                if (!"POST".equals(method)) {
                    return Router.badArgs("该端点只支持 POST（JSON body）");
                }
                return storageWrite(ctx, query, body);
            } else if ("/api/apps".equals(path)) {
                if (!"GET".equals(method)) {
                    return Router.badArgs("该端点只支持 GET");
                }
                return apps(ctx);
            }
            Router.Response r = Router.badArgs("未知端点：" + path);
            return new Router.Response(404, r.json);
        } catch (SecurityException e) {
            return Router.unavailable("系统拒绝访问：" + e.getMessage());
        } catch (Exception e) {
            return Router.unavailable(e.getMessage() == null ? "内部错误" : e.getMessage());
        }
    }

    // ---- 1. ping ----

    private static Router.Response ping() throws JSONException {
        JSONObject d = new JSONObject();
        d.put("name", NAME);
        d.put("version", VERSION);
        return Router.ok(d);
    }

    private static Router.Response deviceInfo(Context ctx) throws JSONException {
        JSONObject d = new JSONObject();
        d.put("manufacturer", Build.MANUFACTURER);
        d.put("model", Build.MODEL);
        d.put("android", Build.VERSION.RELEASE);
        d.put("sdk", Build.VERSION.SDK_INT);
        return Router.ok(d);
    }

    private static Router.Response battery(Context ctx) throws JSONException {
        Intent b = ctx.registerReceiver(null, new IntentFilter(Intent.ACTION_BATTERY_CHANGED));
        JSONObject d = new JSONObject();
        if (b == null) {
            d.put("present", false);
            return Router.ok(d);
        }
        int level = b.getIntExtra(BatteryManager.EXTRA_LEVEL, -1);
        int scale = b.getIntExtra(BatteryManager.EXTRA_SCALE, 100);
        int status = b.getIntExtra(BatteryManager.EXTRA_STATUS, -1);
        int health = b.getIntExtra(BatteryManager.EXTRA_HEALTH, -1);
        int temp = b.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, 0);
        int pct = scale > 0 && level >= 0 ? (level * 100 / scale) : -1;
        d.put("percent", pct);
        d.put("charging", status == BatteryManager.BATTERY_STATUS_CHARGING
                || status == BatteryManager.BATTERY_STATUS_FULL);
        d.put("status", batteryStatus(status));
        d.put("health", batteryHealth(health));
        d.put("temperature_c", temp / 10.0);
        return Router.ok(d);
    }

    private static String batteryStatus(int s) {
        switch (s) {
            case BatteryManager.BATTERY_STATUS_CHARGING: return "charging";
            case BatteryManager.BATTERY_STATUS_DISCHARGING: return "discharging";
            case BatteryManager.BATTERY_STATUS_FULL: return "full";
            case BatteryManager.BATTERY_STATUS_NOT_CHARGING: return "not_charging";
            default: return "unknown";
        }
    }

    private static String batteryHealth(int h) {
        switch (h) {
            case BatteryManager.BATTERY_HEALTH_GOOD: return "good";
            case BatteryManager.BATTERY_HEALTH_OVERHEAT: return "overheat";
            case BatteryManager.BATTERY_HEALTH_DEAD: return "dead";
            case BatteryManager.BATTERY_HEALTH_OVER_VOLTAGE: return "over_voltage";
            case BatteryManager.BATTERY_HEALTH_COLD: return "cold";
            default: return "unknown";
        }
    }

    // ---- 4/5. 短信 ----

    private static Router.Response smsInbox(Context ctx, Map<String, String> query) throws Exception {
        if (!granted(ctx, Manifest.permission.READ_SMS)) {
            return Router.denied("短信权限未授予：请到手机「设置 → 应用 → "
                    + "droid-mcp-companion → 权限」中允许读取短信");
        }
        int limit = intArg(query, null, "limit", 20, 1, 200);
        int offset = intArg(query, null, "offset", 0, 0, 10000);
        JSONArray arr = new JSONArray();
        ContentResolver cr = ctx.getContentResolver();
        Cursor c = null;
        try {
            c = cr.query(Telephony.Sms.Inbox.CONTENT_URI,
                    new String[]{Telephony.Sms.ADDRESS, Telephony.Sms.BODY,
                            Telephony.Sms.DATE, Telephony.Sms.TYPE},
                    null, null, Telephony.Sms.DATE + " DESC");
            if (c != null) {
                int iAddr = c.getColumnIndex(Telephony.Sms.ADDRESS);
                int iBody = c.getColumnIndex(Telephony.Sms.BODY);
                int iDate = c.getColumnIndex(Telephony.Sms.DATE);
                int iType = c.getColumnIndex(Telephony.Sms.TYPE);
                int pos = 0;
                while (c.moveToNext() && arr.length() < limit) {
                    if (pos++ < offset) {
                        continue;
                    }
                    JSONObject m = new JSONObject();
                    m.put("address", iAddr >= 0 ? c.getString(iAddr) : JSONObject.NULL);
                    m.put("body", iBody >= 0 ? c.getString(iBody) : JSONObject.NULL);
                    m.put("date", iDate >= 0 ? c.getLong(iDate) : JSONObject.NULL);
                    m.put("type", iType >= 0 ? c.getInt(iType) : JSONObject.NULL);
                    arr.put(m);
                }
            }
        } finally {
            if (c != null) {
                c.close();
            }
        }
        JSONObject d = new JSONObject();
        d.put("messages", arr);
        d.put("limit", limit);
        d.put("offset", offset);
        return Router.ok(d);
    }

    private static Router.Response smsSend(Context ctx, Map<String, String> query, JSONObject body)
            throws Exception {
        if (!Store.isSmsAllowed(ctx)) {
            return Router.denied("App 内「允许发送短信」开关未打开："
                    + "请在 droid-mcp-companion 首页勾选后再试");
        }
        if (!granted(ctx, Manifest.permission.SEND_SMS)) {
            return Router.denied("发送短信权限未授予：请到手机「设置 → 应用 → "
                    + "droid-mcp-companion → 权限」中允许发送短信");
        }
        String to = strArg(query, body, "to", null);
        String text = strArg(query, body, "text", strArg(query, body, "body", null));
        if (to == null || to.isEmpty() || text == null || text.isEmpty()) {
            return Router.badArgs("缺少参数：to、body（text）必填");
        }
        SmsManager sms = SmsManager.getDefault();
        ArrayList<String> parts = sms.divideMessage(text);
        for (int i = 0; i < parts.size(); i++) {
            sms.sendTextMessage(to, null, parts.get(i), null, null);
        }
        JSONObject d = new JSONObject();
        d.put("sent", true);
        d.put("to", to);
        d.put("parts", parts.size());
        return Router.ok(d);
    }

    // ---- 6/7. 通话 ----

    private static Router.Response callLog(Context ctx, Map<String, String> query) throws Exception {
        if (!granted(ctx, Manifest.permission.READ_CALL_LOG)) {
            return Router.denied("通话记录权限未授予：请到手机「设置 → 应用 → "
                    + "droid-mcp-companion → 权限」中允许读取通话记录");
        }
        int limit = intArg(query, null, "limit", 20, 1, 200);
        JSONArray arr = new JSONArray();
        Cursor c = null;
        try {
            c = ctx.getContentResolver().query(CallLog.Calls.CONTENT_URI,
                    new String[]{CallLog.Calls.NUMBER, CallLog.Calls.CACHED_NAME,
                            CallLog.Calls.DATE, CallLog.Calls.DURATION, CallLog.Calls.TYPE},
                    null, null, CallLog.Calls.DATE + " DESC");
            if (c != null) {
                int iNum = c.getColumnIndex(CallLog.Calls.NUMBER);
                int iName = c.getColumnIndex(CallLog.Calls.CACHED_NAME);
                int iDate = c.getColumnIndex(CallLog.Calls.DATE);
                int iDur = c.getColumnIndex(CallLog.Calls.DURATION);
                int iType = c.getColumnIndex(CallLog.Calls.TYPE);
                while (c.moveToNext() && arr.length() < limit) {
                    JSONObject m = new JSONObject();
                    m.put("number", iNum >= 0 ? c.getString(iNum) : JSONObject.NULL);
                    m.put("name", iName >= 0 ? c.getString(iName) : JSONObject.NULL);
                    m.put("date", iDate >= 0 ? c.getLong(iDate) : JSONObject.NULL);
                    m.put("duration", iDur >= 0 ? c.getLong(iDur) : 0);
                    int t = iType >= 0 ? c.getInt(iType) : 0;
                    m.put("type", callType(t));
                    arr.put(m);
                }
            }
        } finally {
            if (c != null) {
                c.close();
            }
        }
        JSONObject d = new JSONObject();
        d.put("calls", arr);
        d.put("limit", limit);
        return Router.ok(d);
    }

    private static String callType(int t) {
        switch (t) {
            case CallLog.Calls.INCOMING_TYPE: return "incoming";
            case CallLog.Calls.OUTGOING_TYPE: return "outgoing";
            case CallLog.Calls.MISSED_TYPE: return "missed";
            case CallLog.Calls.REJECTED_TYPE: return "rejected";
            case CallLog.Calls.BLOCKED_TYPE: return "blocked";
            default: return "unknown";
        }
    }

    private static Router.Response callDial(Context ctx, Map<String, String> query, JSONObject body)
            throws Exception {
        if (!Store.isDialAllowed(ctx)) {
            return Router.denied("App 内「允许直接拨号」开关未打开："
                    + "请在 droid-mcp-companion 首页勾选后再试");
        }
        if (!granted(ctx, Manifest.permission.CALL_PHONE)) {
            return Router.denied("拨号权限未授予：请到手机「设置 → 应用 → "
                    + "droid-mcp-companion → 权限」中允许拨打电话");
        }
        String number = strArg(query, body, "number", null);
        if (number == null || number.isEmpty()) {
            return Router.badArgs("缺少参数：number 必填");
        }
        Intent i = new Intent(Intent.ACTION_CALL, Uri.parse("tel:" + number));
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        ctx.startActivity(i);
        JSONObject d = new JSONObject();
        d.put("dialing", true);
        d.put("number", number);
        return Router.ok(d);
    }

    // ---- 8. 通讯录 ----

    private static Router.Response contacts(Context ctx) throws Exception {
        if (!granted(ctx, Manifest.permission.READ_CONTACTS)) {
            return Router.denied("通讯录权限未授予：请到手机「设置 → 应用 → "
                    + "droid-mcp-companion → 权限」中允许读取通讯录");
        }
        JSONArray arr = new JSONArray();
        Cursor c = null;
        try {
            c = ctx.getContentResolver().query(
                    ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
                    new String[]{ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,
                            ContactsContract.CommonDataKinds.Phone.NUMBER},
                    null, null,
                    ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME + " ASC");
            if (c != null) {
                int iName = c.getColumnIndex(
                        ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME);
                int iNum = c.getColumnIndex(
                        ContactsContract.CommonDataKinds.Phone.NUMBER);
                while (c.moveToNext() && arr.length() < 2000) {
                    JSONObject m = new JSONObject();
                    m.put("name", iName >= 0 ? c.getString(iName) : JSONObject.NULL);
                    m.put("number", iNum >= 0 ? c.getString(iNum) : JSONObject.NULL);
                    arr.put(m);
                }
            }
        } finally {
            if (c != null) {
                c.close();
            }
        }
        JSONObject d = new JSONObject();
        d.put("contacts", arr);
        d.put("count", arr.length());
        return Router.ok(d);
    }

    // ---- 9/10. 剪贴板 ----

    private static Router.Response clipboardGet(Context ctx) throws JSONException {
        ClipboardManager cm = (ClipboardManager) ctx.getSystemService(Context.CLIPBOARD_SERVICE);
        String text = null;
        if (cm != null && cm.hasPrimaryClip()) {
            ClipData clip = cm.getPrimaryClip();
            if (clip != null && clip.getItemCount() > 0) {
                CharSequence cs = clip.getItemAt(0).coerceToText(ctx);
                if (cs != null) {
                    text = cs.toString();
                }
            }
        }
        JSONObject d = new JSONObject();
        d.put("text", text == null ? JSONObject.NULL : text);
        return Router.ok(d);
    }

    private static Router.Response clipboardSet(Context ctx, Map<String, String> query, JSONObject body)
            throws JSONException {
        String text = strArg(query, body, "text", null);
        if (text == null) {
            return Router.badArgs("缺少参数：text 必填");
        }
        ClipboardManager cm = (ClipboardManager) ctx.getSystemService(Context.CLIPBOARD_SERVICE);
        if (cm == null) {
            return Router.unavailable("这台手机不支持剪贴板");
        }
        cm.setPrimaryClip(ClipData.newPlainText("droid-mcp", text));
        JSONObject d = new JSONObject();
        d.put("set", true);
        return Router.ok(d);
    }

    // ---- 11/12/13/14. 通知 / Toast / 震动 ----

    private static Router.Response notify(Context ctx, Map<String, String> query, JSONObject body)
            throws Exception {
        if (!notificationsEnabled(ctx)) {
            return Router.denied("通知权限未授予：请到手机「设置 → 应用 → "
                    + "droid-mcp-companion → 通知」中允许发送通知");
        }
        String content = strArg(query, body, "content", null);
        if (content == null || content.isEmpty()) {
            return Router.badArgs("缺少参数：content 必填");
        }
        String title = strArg(query, body, "title", "droid-mcp");
        int id = intArg(query, body, "id", 1, 0, Integer.MAX_VALUE);
        NotificationManager nm =
                (NotificationManager) ctx.getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm == null) {
            return Router.unavailable("这台手机不支持通知");
        }
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel ch = new NotificationChannel(NOTIFY_CHANNEL,
                    "droid-mcp", NotificationManager.IMPORTANCE_DEFAULT);
            nm.createNotificationChannel(ch);
        }
        Notification.Builder b;
        if (Build.VERSION.SDK_INT >= 26) {
            b = new Notification.Builder(ctx, NOTIFY_CHANNEL);
        } else {
            b = new Notification.Builder(ctx);
        }
        b.setContentTitle(title)
                .setContentText(content)
                .setSmallIcon(android.R.drawable.sym_def_app_icon)
                .setAutoCancel(true);
        nm.notify(id, b.build());
        JSONObject d = new JSONObject();
        d.put("notified", true);
        d.put("id", id);
        return Router.ok(d);
    }

    private static boolean notificationsEnabled(Context ctx) {
        if (Build.VERSION.SDK_INT >= 33
                && !granted(ctx, Manifest.permission.POST_NOTIFICATIONS)) {
            return false;
        }
        NotificationManager nm =
                (NotificationManager) ctx.getSystemService(Context.NOTIFICATION_SERVICE);
        return nm == null || nm.areNotificationsEnabled();
    }

    private static Router.Response notificationRemove(Context ctx,
                                                      Map<String, String> query, JSONObject body)
            throws Exception {
        Integer id = intOrNull(query, body, "id");
        if (id == null) {
            return Router.badArgs("缺少参数：id 必填");
        }
        NotificationManager nm =
                (NotificationManager) ctx.getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm == null) {
            return Router.unavailable("这台手机不支持通知");
        }
        nm.cancel(id);
        JSONObject d = new JSONObject();
        d.put("removed", true);
        d.put("id", id);
        return Router.ok(d);
    }

    private static Router.Response toast(final Context ctx,
                                         Map<String, String> query, JSONObject body)
            throws JSONException {
        final String text = strArg(query, body, "text", null);
        if (text == null || text.isEmpty()) {
            return Router.badArgs("缺少参数：text 必填");
        }
        // 连接处理线程没有 Looper，切回主线程弹 Toast。
        new Handler(Looper.getMainLooper()).post(new Runnable() {
            @Override
            public void run() {
                Toast.makeText(ctx.getApplicationContext(), text, Toast.LENGTH_LONG).show();
            }
        });
        JSONObject d = new JSONObject();
        d.put("shown", true);
        return Router.ok(d);
    }

    private static Router.Response vibrate(Context ctx,
                                           Map<String, String> query, JSONObject body)
            throws Exception {
        int ms = intArg(query, body, "ms", 100, 1, 10000);
        Vibrator v = (Vibrator) ctx.getSystemService(Context.VIBRATOR_SERVICE);
        if (v == null || !v.hasVibrator()) {
            return Router.unavailable("这台手机不支持震动");
        }
        if (Build.VERSION.SDK_INT >= 26) {
            v.vibrate(VibrationEffect.createOneShot(ms, VibrationEffect.DEFAULT_AMPLITUDE));
        } else {
            v.vibrate(ms);
        }
        JSONObject d = new JSONObject();
        d.put("vibrated", true);
        d.put("ms", ms);
        return Router.ok(d);
    }

    // ---- 15. Wi-Fi ----

    private static Router.Response wifi(Context ctx) throws Exception {
        WifiManager wm = (WifiManager) ctx.getApplicationContext()
                .getSystemService(Context.WIFI_SERVICE);
        if (wm == null || !wm.isWifiEnabled()) {
            return Router.unavailable("Wi-Fi 未打开或这台手机不支持");
        }
        WifiInfo info = wm.getConnectionInfo();
        JSONObject d = new JSONObject();
        d.put("ssid", info.getSSID());
        d.put("bssid", info.getBSSID());
        d.put("rssi", info.getRssi());
        return Router.ok(d);
    }

    // ---- 16. 定位 ----

    private static Router.Response location(Context ctx, Map<String, String> query) throws Exception {
        if (!granted(ctx, Manifest.permission.ACCESS_FINE_LOCATION)
                && !granted(ctx, Manifest.permission.ACCESS_COARSE_LOCATION)) {
            return Router.denied("定位权限未授予：请到手机「设置 → 应用 → "
                    + "droid-mcp-companion → 权限」中允许获取位置");
        }
        String provider = strArg(query, null, "provider", "network");
        String want = LocationManager.NETWORK_PROVIDER;
        if ("gps".equalsIgnoreCase(provider)) {
            want = LocationManager.GPS_PROVIDER;
        }
        LocationManager lm = (LocationManager) ctx.getSystemService(Context.LOCATION_SERVICE);
        if (lm == null || !lm.isProviderEnabled(want)) {
            return Router.unavailable("定位不可用：请打开系统定位后再试");
        }
        Location loc = lm.getLastKnownLocation(want);
        if (loc == null) {
            return Router.unavailable("暂无定位结果：请打开系统定位并稍候再试");
        }
        JSONObject d = new JSONObject();
        d.put("provider", want);
        d.put("lat", loc.getLatitude());
        d.put("lng", loc.getLongitude());
        d.put("accuracy", (double) loc.getAccuracy());
        d.put("time", loc.getTime());
        return Router.ok(d);
    }

    // ---- 17/18/19. 存储（沙盒：Download + App 外部目录） ----

    private static File jailCheck(Context ctx, String path) throws IOException {
        File base = Environment.getExternalStoragePublicDirectory(
                Environment.DIRECTORY_DOWNLOADS);
        File f = new File(path);
        if (!f.isAbsolute()) {
            f = new File(base, path);
        }
        String canon = f.getCanonicalPath();
        boolean manageAll = Build.VERSION.SDK_INT >= 30
                && Environment.isExternalStorageManager();
        if (!manageAll) {
            List<String> roots = new ArrayList<String>();
            roots.add(new File(base.getCanonicalPath()).getCanonicalPath());
            File ext = ctx.getExternalFilesDir(null);
            if (ext != null) {
                roots.add(ext.getCanonicalPath());
            }
            boolean inside = false;
            for (int i = 0; i < roots.size(); i++) {
                String r = roots.get(i);
                if (canon.equals(r) || canon.startsWith(r + "/")) {
                    inside = true;
                    break;
                }
            }
            if (!inside) {
                return null;
            }
        }
        return new File(canon);
    }

    private static String deniedStorage() {
        return "超出沙盒目录：默认只允许 Download 目录与 App 外部目录；"
                + "完整 /sdcard 访问请到手机「设置 → 应用 → 特殊应用权限 → "
                + "所有文件访问权限」中允许本应用";
    }

    private static Router.Response storageList(Context ctx, Map<String, String> query)
            throws Exception {
        String arg = strArg(query, null, "path", null);
        if (arg == null || arg.isEmpty()) {
            arg = Environment.getExternalStoragePublicDirectory(
                    Environment.DIRECTORY_DOWNLOADS).getAbsolutePath();
        }
        File dir = jailCheck(ctx, arg);
        if (dir == null) {
            return Router.denied(deniedStorage());
        }
        if (!dir.exists() || !dir.isDirectory()) {
            return Router.badArgs("目录不存在：" + arg);
        }
        File[] files = dir.listFiles();
        JSONArray arr = new JSONArray();
        if (files != null) {
            for (int i = 0; i < files.length; i++) {
                JSONObject m = new JSONObject();
                m.put("name", files[i].getName());
                m.put("is_dir", files[i].isDirectory());
                m.put("size", files[i].isDirectory() ? 0 : files[i].length());
                m.put("mtime", files[i].lastModified());
                arr.put(m);
            }
        }
        JSONObject d = new JSONObject();
        d.put("path", dir.getAbsolutePath());
        d.put("files", arr);
        return Router.ok(d);
    }

    private static Router.Response storageRead(Context ctx, Map<String, String> query)
            throws Exception {
        String arg = strArg(query, null, "path", null);
        if (arg == null || arg.isEmpty()) {
            return Router.badArgs("缺少参数：path 必填");
        }
        int maxBytes = intArg(query, null, "max_bytes", 64 * 1024, 1, 1024 * 1024);
        File f = jailCheck(ctx, arg);
        if (f == null) {
            return Router.denied(deniedStorage());
        }
        if (!f.exists() || !f.isFile()) {
            return Router.badArgs("文件不存在：" + arg);
        }
        byte[] data = readFully(new FileInputStream(f), maxBytes + 1);
        boolean truncated = data.length > maxBytes;
        int n = truncated ? maxBytes : data.length;
        String text = new String(data, 0, n, StandardCharsets.UTF_8);
        JSONObject d = new JSONObject();
        d.put("path", f.getAbsolutePath());
        d.put("size", f.length());
        d.put("truncated", truncated);
        d.put("text", text);
        return Router.ok(d);
    }

    private static Router.Response storageWrite(Context ctx,
                                                Map<String, String> query, JSONObject body)
            throws Exception {
        String arg = strArg(query, body, "path", null);
        String text = strArg(query, body, "text", null);
        if (arg == null || arg.isEmpty() || text == null) {
            return Router.badArgs("缺少参数：path、text 必填");
        }
        boolean overwrite = boolArg(query, body, "overwrite", false);
        File f = jailCheck(ctx, arg);
        if (f == null) {
            return Router.denied(deniedStorage());
        }
        if (f.exists() && !overwrite) {
            return Router.badArgs("文件已存在：如需覆盖请传 overwrite=true");
        }
        File parent = f.getParentFile();
        if (parent != null && !parent.exists() && !parent.mkdirs()) {
            return Router.unavailable("无法创建目录：" + parent.getAbsolutePath());
        }
        byte[] bytes = text.getBytes(StandardCharsets.UTF_8);
        OutputStream out = null;
        try {
            out = new FileOutputStream(f, false);
            out.write(bytes);
        } finally {
            if (out != null) {
                try {
                    out.close();
                } catch (IOException ignored) {
                }
            }
        }
        JSONObject d = new JSONObject();
        d.put("written", true);
        d.put("path", f.getAbsolutePath());
        d.put("bytes", bytes.length);
        return Router.ok(d);
    }

    // ---- 20. 已安装应用 ----

    private static Router.Response apps(Context ctx) throws Exception {
        PackageManager pm = ctx.getPackageManager();
        List<ApplicationInfo> installed =
                pm.getInstalledApplications(PackageManager.GET_META_DATA);
        JSONArray arr = new JSONArray();
        for (int i = 0; i < installed.size(); i++) {
            ApplicationInfo ai = installed.get(i);
            boolean system = (ai.flags & ApplicationInfo.FLAG_SYSTEM) != 0;
            // 去掉无启动图标的系统项。
            if (system && pm.getLaunchIntentForPackage(ai.packageName) == null) {
                continue;
            }
            JSONObject m = new JSONObject();
            m.put("package", ai.packageName);
            m.put("name", String.valueOf(pm.getApplicationLabel(ai)));
            arr.put(m);
        }
        JSONObject d = new JSONObject();
        d.put("apps", arr);
        d.put("count", arr.length());
        return Router.ok(d);
    }

    // ---- 小工具 ----

    private static boolean granted(Context ctx, String perm) {
        return ctx.checkSelfPermission(perm) == PackageManager.PERMISSION_GRANTED;
    }

    private static String strArg(Map<String, String> query, JSONObject body,
                                 String key, String def) {
        if (query != null && query.containsKey(key)) {
            return query.get(key);
        }
        if (body != null && body.has(key) && !body.isNull(key)) {
            return body.optString(key, def);
        }
        return def;
    }

    private static int intArg(Map<String, String> query, JSONObject body,
                              String key, int def, int min, int max) throws JSONException {
        Integer v = intOrNull(query, body, key);
        if (v == null) {
            return def;
        }
        if (v < min) {
            return min;
        }
        if (v > max) {
            return max;
        }
        return v;
    }

    private static Integer intOrNull(Map<String, String> query, JSONObject body, String key)
            throws JSONException {
        String raw = null;
        if (query != null && query.containsKey(key)) {
            raw = query.get(key);
        } else if (body != null && body.has(key) && !body.isNull(key)) {
            Object o = body.get(key);
            if (o instanceof Number) {
                return ((Number) o).intValue();
            }
            raw = String.valueOf(o);
        } else {
            return null;
        }
        try {
            return Integer.parseInt(raw.trim());
        } catch (NumberFormatException e) {
            throw new JSONException("参数 " + key + " 不是整数：" + raw);
        }
    }

    private static boolean boolArg(Map<String, String> query, JSONObject body,
                                   String key, boolean def) {
        String raw = null;
        if (query != null && query.containsKey(key)) {
            raw = query.get(key);
        } else if (body != null && body.has(key) && !body.isNull(key)) {
            Object o;
            try {
                o = body.get(key);
            } catch (JSONException e) {
                return def;
            }
            if (o instanceof Boolean) {
                return (Boolean) o;
            }
            raw = String.valueOf(o);
        } else {
            return def;
        }
        return "true".equalsIgnoreCase(raw) || "1".equals(raw);
    }

    private static byte[] readFully(InputStream in, int cap) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buf = new byte[8192];
        int total = 0;
        try {
            while (true) {
                int n = in.read(buf);
                if (n < 0) {
                    break;
                }
                if (total + n > cap) {
                    out.write(buf, 0, cap - total);
                    // 继续消费丢弃，避免调用方截断语义混乱。
                    total = cap + 1;
                    break;
                }
                out.write(buf, 0, n);
                total += n;
            }
        } finally {
            try {
                in.close();
            } catch (IOException ignored) {
            }
        }
        if (total > cap) {
            byte[] r = out.toByteArray();
            byte[] over = new byte[cap + 1];
            System.arraycopy(r, 0, over, 0, cap + 1);
            return over;
        }
        return out.toByteArray();
    }
}
