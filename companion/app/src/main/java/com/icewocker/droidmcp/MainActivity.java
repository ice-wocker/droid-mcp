package com.icewocker.droidmcp;

import android.Manifest;
import android.app.Activity;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.CompoundButton;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.List;

/**
 * 首页：显示 token、服务开关按钮、权限状态行；
 * 启动时申请 SMS / CONTACTS / CALL_LOG / NOTIFICATIONS(33+) / LOCATION；
 * 短信发送与直接拨号各一个 CheckBox 开关（默认关，对应协议安全边界第 3 条）。
 */
public class MainActivity extends Activity {

    private static final int REQ_STARTUP = 1001;
    private static final int REQ_CALL_PHONE = 1002;

    private TextView tvToken;
    private TextView tvStatus;
    private TextView tvPerm;
    private Button btnStart;
    private Button btnStop;
    private CheckBox cbSms;
    private CheckBox cbDial;

    private boolean pendingDial;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        tvToken = (TextView) findViewById(R.id.tv_token);
        tvStatus = (TextView) findViewById(R.id.tv_status);
        tvPerm = (TextView) findViewById(R.id.tv_perm);
        btnStart = (Button) findViewById(R.id.btn_start);
        btnStop = (Button) findViewById(R.id.btn_stop);
        cbSms = (CheckBox) findViewById(R.id.cb_sms);
        cbDial = (CheckBox) findViewById(R.id.cb_dial);

        cbSms.setChecked(Store.isSmsAllowed(this));
        cbDial.setChecked(Store.isDialAllowed(this));

        cbSms.setOnCheckedChangeListener(new CompoundButton.OnCheckedChangeListener() {
            @Override
            public void onCheckedChanged(CompoundButton buttonView, boolean isChecked) {
                Store.setSmsAllowed(MainActivity.this, isChecked);
                refresh();
            }
        });
        cbDial.setOnCheckedChangeListener(new CompoundButton.OnCheckedChangeListener() {
            @Override
            public void onCheckedChanged(CompoundButton buttonView, boolean isChecked) {
                if (isChecked && !hasPerm(Manifest.permission.CALL_PHONE)) {
                    // 开拨号开关时才申请 CALL_PHONE（启动时不申请）。
                    pendingDial = true;
                    requestPermissions(new String[]{Manifest.permission.CALL_PHONE},
                            REQ_CALL_PHONE);
                    cbDial.setChecked(false);
                    return;
                }
                Store.setDialAllowed(MainActivity.this, isChecked);
                refresh();
            }
        });

        btnStart.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                CompanionService.start(MainActivity.this);
                refresh();
            }
        });
        btnStop.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                CompanionService.stop(MainActivity.this);
                refresh();
            }
        });

        requestPermissions(startupPerms(), REQ_STARTUP);
        refresh();
    }

    @Override
    protected void onResume() {
        super.onResume();
        refresh();
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions,
                                           int[] grantResults) {
        if (requestCode == REQ_CALL_PHONE && pendingDial) {
            pendingDial = false;
            if (grantResults.length > 0
                    && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                Store.setDialAllowed(this, true);
                cbDial.setChecked(true);
            }
        }
        refresh();
    }

    private static String[] startupPerms() {
        List<String> req = new ArrayList<String>();
        req.add(Manifest.permission.SEND_SMS);
        req.add(Manifest.permission.RECEIVE_SMS);
        req.add(Manifest.permission.READ_SMS);
        req.add(Manifest.permission.READ_CONTACTS);
        req.add(Manifest.permission.READ_CALL_LOG);
        req.add(Manifest.permission.ACCESS_FINE_LOCATION);
        req.add(Manifest.permission.ACCESS_COARSE_LOCATION);
        if (Build.VERSION.SDK_INT >= 33) {
            req.add(Manifest.permission.POST_NOTIFICATIONS);
        }
        return req.toArray(new String[0]);
    }

    private boolean hasPerm(String perm) {
        return checkSelfPermission(perm) == PackageManager.PERMISSION_GRANTED;
    }

    private void refresh() {
        tvToken.setText("token：" + Store.getToken(this)
                + "\n局域网地址：http://<手机 IP>:" + CompanionService.PORT
                + "?token=…（或头 Authorization: Bearer）");
        tvStatus.setText(CompanionService.RUNNING ? "服务状态：运行中（端口 "
                + CompanionService.PORT + "）" : "服务状态：未启动");

        String[] all = startupPerms();
        List<String> missing = new ArrayList<String>();
        int ok = 0;
        for (int i = 0; i < all.length; i++) {
            if (hasPerm(all[i])) {
                ok++;
            } else {
                missing.add(shortName(all[i]));
            }
        }
        String line = "权限：" + ok + "/" + all.length + " 已授予";
        if (!missing.isEmpty()) {
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < missing.size(); i++) {
                if (i > 0) {
                    sb.append("、");
                }
                sb.append(missing.get(i));
            }
            line += "，缺：" + sb.toString() + "（去手机「设置 → 应用 → "
                    + "droid-mcp-companion → 权限」开启）";
        }
        tvPerm.setText(line);
    }

    private static String shortName(String perm) {
        int i = perm.lastIndexOf('.');
        return i >= 0 ? perm.substring(i + 1) : perm;
    }
}
