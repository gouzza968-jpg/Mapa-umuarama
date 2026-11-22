package com.mapaumuarama.app;

import android.content.Intent;
import android.content.pm.PackageInfo;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;

import androidx.core.content.FileProvider;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;

/** Atualização do app por dentro: baixa o APK novo e abre o instalador do Android. */
@CapacitorPlugin(name = "AppUpdate")
public class AppUpdatePlugin extends Plugin {
    private volatile int pct = 0;
    private volatile boolean done = false, busy = false;
    private volatile String error = "";

    @PluginMethod
    public void info(PluginCall call) {
        try {
            PackageInfo pi = getContext().getPackageManager().getPackageInfo(getContext().getPackageName(), 0);
            JSObject r = new JSObject();
            r.put("versionName", pi.versionName);
            r.put("versionCode", Build.VERSION.SDK_INT >= 28 ? pi.getLongVersionCode() : pi.versionCode);
            call.resolve(r);
        } catch (Exception e) {
            call.reject("info");
        }
    }

    @PluginMethod
    public void canInstall(PluginCall call) {
        JSObject r = new JSObject();
        r.put("ok", Build.VERSION.SDK_INT < 26 || getContext().getPackageManager().canRequestPackageInstalls());
        call.resolve(r);
    }

    @PluginMethod
    public void openInstallSettings(PluginCall call) {
        try {
            Intent i = new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:" + getContext().getPackageName()));
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            getContext().startActivity(i);
            call.resolve();
        } catch (Exception e) {
            call.reject("settings");
        }
    }

    @PluginMethod
    public void download(final PluginCall call) {
        final String url = call.getString("url", "");
        if (url.isEmpty()) { call.reject("url"); return; }
        if (busy) { call.resolve(); return; }
        busy = true; done = false; pct = 0; error = "";
        new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
                    c.setConnectTimeout(15000);
                    c.setReadTimeout(30000);
                    c.setInstanceFollowRedirects(true);
                    int code = c.getResponseCode();
                    if (code != 200) throw new Exception("HTTP " + code);
                    long total = c.getContentLengthLong();
                    File out = new File(getContext().getCacheDir(), "update.apk");
                    InputStream in = c.getInputStream();
                    FileOutputStream os = new FileOutputStream(out);
                    byte[] buf = new byte[32768];
                    long got = 0;
                    int n;
                    while ((n = in.read(buf)) > 0) {
                        os.write(buf, 0, n);
                        got += n;
                        if (total > 0) pct = (int) (got * 100 / total);
                    }
                    os.close();
                    in.close();
                    if (out.length() < 100000) throw new Exception("arquivo inválido");
                    pct = 100;
                    done = true;
                } catch (Exception e) {
                    error = String.valueOf(e.getMessage());
                }
                busy = false;
            }
        }).start();
        call.resolve();
    }

    @PluginMethod
    public void status(PluginCall call) {
        JSObject r = new JSObject();
        r.put("pct", pct);
        r.put("done", done);
        r.put("busy", busy);
        r.put("error", error);
        call.resolve(r);
    }

    @PluginMethod
    public void install(PluginCall call) {
        try {
            File f = new File(getContext().getCacheDir(), "update.apk");
            Uri u = FileProvider.getUriForFile(getContext(), getContext().getPackageName() + ".fileprovider", f);
            Intent i = new Intent(Intent.ACTION_VIEW);
            i.setDataAndType(u, "application/vnd.android.package-archive");
            i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
            getContext().startActivity(i);
            call.resolve();
        } catch (Exception e) {
            call.reject("install: " + e.getMessage());
        }
    }

    /** Abre a tela de compartilhar do Android com um texto (link de download). */
    @PluginMethod
    public void shareText(PluginCall call) {
        try {
            Intent i = new Intent(Intent.ACTION_SEND);
            i.setType("text/plain");
            i.putExtra(Intent.EXTRA_TEXT, call.getString("text", ""));
            Intent ch = Intent.createChooser(i, call.getString("title", "Compartilhar"));
            ch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            getContext().startActivity(ch);
            call.resolve();
        } catch (Exception e) {
            call.reject("share");
        }
    }

    /** Compartilha o próprio APK instalado (funciona sem internet, ex.: pelo WhatsApp ou Bluetooth). */
    @PluginMethod
    public void shareApk(final PluginCall call) {
        new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    File src = new File(getContext().getApplicationInfo().sourceDir);
                    File dir = new File(getContext().getCacheDir(), "compartilhar");
                    dir.mkdirs();
                    File out = new File(dir, "Mapa-Umuarama.apk");
                    java.io.FileInputStream in = new java.io.FileInputStream(src);
                    FileOutputStream os = new FileOutputStream(out);
                    byte[] buf = new byte[65536];
                    int n;
                    while ((n = in.read(buf)) > 0) os.write(buf, 0, n);
                    os.close();
                    in.close();
                    final Uri u = FileProvider.getUriForFile(getContext(), getContext().getPackageName() + ".fileprovider", out);
                    final Intent i = new Intent(Intent.ACTION_SEND);
                    i.setType("application/vnd.android.package-archive");
                    i.putExtra(Intent.EXTRA_STREAM, u);
                    i.putExtra(Intent.EXTRA_TEXT, call.getString("text", ""));
                    i.setClipData(android.content.ClipData.newRawUri("Mapa-Umuarama.apk", u));
                    i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                    final Intent ch = Intent.createChooser(i, "Enviar o app");
                    ch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_GRANT_READ_URI_PERMISSION);
                    getActivity().runOnUiThread(new Runnable() {
                        @Override
                        public void run() {
                            try { getContext().startActivity(ch); call.resolve(); }
                            catch (Exception e) { call.reject("share"); }
                        }
                    });
                } catch (Exception e) {
                    call.reject("apk: " + e.getMessage());
                }
            }
        }).start();
    }
}
