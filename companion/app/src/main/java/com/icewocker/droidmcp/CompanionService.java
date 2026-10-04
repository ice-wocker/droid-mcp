package com.icewocker.droidmcp;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.ServerSocket;
import java.net.Socket;
import java.net.SocketTimeoutException;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import org.json.JSONObject;

/**
 * 前台服务：通知常驻，ServerSocket 监听 4833，线程池处理，每个连接 10 秒超时。
 *
 * 纯手写 HTTP（ServerSocket + 手工解析请求行/头/body），无任何 HTTP 库。
 */
public class CompanionService extends Service {

    public static final int PORT = 4833;
    /** 供 MainActivity 显示服务状态。 */
    public static volatile boolean RUNNING = false;

    private static final int NOTIF_ID = 1;
    private static final String CHANNEL_ID = "companion";
    private static final int SOCKET_TIMEOUT_MS = 10_000;
    private static final int MAX_BODY_BYTES = 2 * 1024 * 1024;

    private ServerSocket server;
    private ExecutorService pool;
    private Thread acceptThread;
    private volatile boolean running;

    public static void start(Context ctx) {
        Intent i = new Intent(ctx, CompanionService.class);
        if (Build.VERSION.SDK_INT >= 26) {
            ctx.startForegroundService(i);
        } else {
            ctx.startService(i);
        }
    }

    public static void stop(Context ctx) {
        ctx.stopService(new Intent(ctx, CompanionService.class));
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public void onCreate() {
        super.onCreate();
        Store.getToken(this); // 首次启动即生成 token
        startFg();
        startServer();
        RUNNING = true;
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        running = false;
        RUNNING = false;
        if (server != null) {
            try {
                server.close();
            } catch (IOException ignored) {
            }
            server = null;
        }
        if (pool != null) {
            pool.shutdownNow();
            pool = null;
        }
        if (Build.VERSION.SDK_INT >= 24) {
            stopForeground(STOP_FOREGROUND_REMOVE);
        } else {
            stopForeground(true);
        }
        super.onDestroy();
    }

    private void startFg() {
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationManager nm =
                    (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
            if (nm != null) {
                NotificationChannel ch = new NotificationChannel(CHANNEL_ID,
                        "droid-mcp companion", NotificationManager.IMPORTANCE_LOW);
                ch.setDescription("droid-mcp 手机伴侣服务常驻通知");
                nm.createNotificationChannel(ch);
            }
        }
        Intent i = new Intent(this, MainActivity.class);
        PendingIntent pi = PendingIntent.getActivity(this, 0, i,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder b;
        if (Build.VERSION.SDK_INT >= 26) {
            b = new Notification.Builder(this, CHANNEL_ID);
        } else {
            b = new Notification.Builder(this);
        }
        b.setContentTitle("droid-mcp companion 运行中")
                .setContentText("监听端口 " + PORT + "，token 请在 App 首页查看")
                .setSmallIcon(android.R.drawable.sym_def_app_icon)
                .setContentIntent(pi)
                .setOngoing(true);
        Notification n = b.build();
        if (Build.VERSION.SDK_INT >= 29) {
            startForeground(NOTIF_ID, n,
                    android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC);
        } else {
            startForeground(NOTIF_ID, n);
        }
    }

    private void startServer() {
        pool = Executors.newFixedThreadPool(8);
        running = true;
        acceptThread = new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    server = new ServerSocket(PORT);
                    while (running) {
                        try {
                            final Socket s = server.accept();
                            pool.execute(new Runnable() {
                                @Override
                                public void run() {
                                    handleConn(s);
                                }
                            });
                        } catch (IOException e) {
                            if (running) {
                                try {
                                    Thread.sleep(500);
                                } catch (InterruptedException ie) {
                                    return;
                                }
                            }
                        }
                    }
                } catch (IOException e) {
                    // 端口被占 / 无 INTERNET 权限等：服务保持存活，由上层查看日志。
                    android.util.Log.e("CompanionService", "listen 4833 失败", e);
                }
            }
        }, "companion-accept");
        acceptThread.start();
    }

    private void handleConn(Socket s) {
        try {
            s.setSoTimeout(SOCKET_TIMEOUT_MS);
            InputStream in = s.getInputStream();
            String reqLine = readLine(in);
            if (reqLine == null || reqLine.isEmpty()) {
                return;
            }
            String[] parts = reqLine.split(" ", 3);
            if (parts.length < 2) {
                writeResp(s, 400, Router.errJson("bad_args", "请求行非法"));
                return;
            }
            String method = parts[0].toUpperCase(Locale.US);
            String target = parts[1];
            Map<String, String> headers = new HashMap<String, String>();
            while (true) {
                String line = readLine(in);
                if (line == null || line.isEmpty()) {
                    break;
                }
                int c = line.indexOf(':');
                if (c > 0) {
                    headers.put(line.substring(0, c).trim().toLowerCase(Locale.US),
                            line.substring(c + 1).trim());
                }
            }
            int len = 0;
            try {
                len = Integer.parseInt(headers.get("content-length"));
            } catch (Exception ignored) {
                len = 0;
            }
            if (len < 0) {
                len = 0;
            }
            if (len > MAX_BODY_BYTES) {
                writeResp(s, 400, Router.errJson("bad_args", "body 过大"));
                return;
            }
            byte[] bodyBytes = readFully(in, len);
            JSONObject body;
            if (bodyBytes.length == 0) {
                body = new JSONObject();
            } else {
                try {
                    body = new JSONObject(new String(bodyBytes, StandardCharsets.UTF_8));
                } catch (Exception e) {
                    writeResp(s, 400, Router.errJson("bad_args", "JSON body 解析失败"));
                    return;
                }
            }
            Router.Response r = Router.route(this, method, target, headers, body);
            writeResp(s, r.status, r.json);
        } catch (SocketTimeoutException e) {
            try {
                writeResp(s, 408, Router.errJson("bad_args", "请求超时（10 秒）"));
            } catch (Exception ignored) {
            }
        } catch (Exception ignored) {
        } finally {
            try {
                s.close();
            } catch (IOException ignored) {
            }
        }
    }

    /** 按行读（\n 结尾，去 \r），超时/断开返回 null。 */
    private static String readLine(InputStream in) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        while (true) {
            int b = in.read();
            if (b < 0) {
                return out.size() == 0 ? null : new String(out.toByteArray(),
                        StandardCharsets.UTF_8);
            }
            if (b == '\n') {
                break;
            }
            if (b != '\r') {
                out.write(b);
            }
            if (out.size() > 8192) {
                break;
            }
        }
        return new String(out.toByteArray(), StandardCharsets.UTF_8);
    }

    private static byte[] readFully(InputStream in, int len) throws IOException {
        byte[] buf = new byte[len];
        int off = 0;
        while (off < len) {
            int n = in.read(buf, off, len - off);
            if (n < 0) {
                break;
            }
            off += n;
        }
        if (off == len) {
            return buf;
        }
        byte[] r = new byte[off];
        System.arraycopy(buf, 0, r, 0, off);
        return r;
    }

    private static void writeResp(Socket s, int status, String json) throws IOException {
        byte[] body = json.getBytes(StandardCharsets.UTF_8);
        String head = "HTTP/1.1 " + status + " " + reason(status) + "\r\n"
                + "Content-Type: application/json; charset=utf-8\r\n"
                + "Content-Length: " + body.length + "\r\n"
                + "Connection: close\r\n"
                + "\r\n";
        OutputStream out = s.getOutputStream();
        out.write(head.getBytes(StandardCharsets.UTF_8));
        out.write(body);
        out.flush();
    }

    private static String reason(int status) {
        switch (status) {
            case 200: return "OK";
            case 400: return "Bad Request";
            case 401: return "Unauthorized";
            case 403: return "Forbidden";
            case 404: return "Not Found";
            case 408: return "Request Timeout";
            case 500: return "Internal Error";
            default: return "OK";
        }
    }
}
