package com.mahadev.avoid;

import android.annotation.SuppressLint;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.PermissionRequest;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import androidx.activity.OnBackPressedCallback;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AppCompatActivity;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

public class MainActivity extends AppCompatActivity {

    private WebView webView;
    private ValueCallback<Uri[]> filePathCallback;

    private final ActivityResultLauncher<Intent> fileChooserLauncher =
            registerForActivityResult(new ActivityResultContracts.StartActivityForResult(), result -> {
                if (filePathCallback == null) return;
                Uri[] results = null;
                if (result.getResultCode() == RESULT_OK && result.getData() != null) {
                    Uri uri = result.getData().getData();
                    if (uri != null) {
                        results = new Uri[]{uri};
                        extractFirebaseFromApk(uri);
                    } else if (result.getData().getClipData() != null) {
                        int count = result.getData().getClipData().getItemCount();
                        results = new Uri[count];
                        for (int i = 0; i < count; i++) {
                            Uri u = result.getData().getClipData().getItemAt(i).getUri();
                            results[i] = u;
                            if (i == 0) extractFirebaseFromApk(u);
                        }
                    }
                }
                filePathCallback.onReceiveValue(results);
                filePathCallback = null;
            });

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        webView = findViewById(R.id.webView);

        WebSettings webSettings = webView.getSettings();
        webSettings.setJavaScriptEnabled(true);
        webSettings.setDomStorageEnabled(true);
        webSettings.setAllowFileAccess(true);
        webSettings.setAllowContentAccess(true);
        webSettings.setJavaScriptCanOpenWindowsAutomatically(true);
        webSettings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        webSettings.setUseWideViewPort(true);
        webSettings.setLoadWithOverviewMode(true);
        webSettings.setMediaPlaybackRequiresUserGesture(false);

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                String url = request.getUrl().toString();
                if (url.startsWith("http://") || url.startsWith("https://") || url.startsWith("file://")) {
                    return false;
                }
                try {
                    Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
                    startActivity(intent);
                    return true;
                } catch (Exception e) {
                    return false;
                }
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                String script = "javascript:(function(){" +
                        "function fixText(){" +
                        "  var walker = document.createTreeWalker(document.body || document.documentElement, NodeFilter.SHOW_TEXT, null, false);" +
                        "  var node;" +
                        "  while(node = walker.nextNode()) {" +
                        "    if(node.nodeValue && /VOID/i.test(node.nodeValue)) {" +
                        "      node.nodeValue = node.nodeValue.replace(/VOID PANEL V5\\.2/gi, 'MAHADEV ADMIN V5.2')" +
                        "                                     .replace(/VOID PANEL/gi, 'MAHADEV ADMIN')" +
                        "                                     .replace(/VOID v5\\.2/gi, 'MAHADEV v5.2')" +
                        "                                     .replace(/VOID V5\\.2/gi, 'MAHADEV V5.2')" +
                        "                                     .replace(/VOID/gi, 'MAHADEV');" +
                        "    }" +
                        "  }" +
                        "}" +
                        "fixText();" +
                        "setInterval(fixText, 250);" +
                        "})();";
                view.evaluateJavascript(script, null);
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView webView, ValueCallback<Uri[]> filePathCallback, FileChooserParams fileChooserParams) {
                if (MainActivity.this.filePathCallback != null) {
                    MainActivity.this.filePathCallback.onReceiveValue(null);
                }
                MainActivity.this.filePathCallback = filePathCallback;

                Intent intent = new Intent(Intent.ACTION_GET_CONTENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                intent.setType("*/*");
                intent.putExtra(Intent.EXTRA_MIME_TYPES, new String[]{"application/vnd.android.package-archive", "application/octet-stream", "*/*"});
                intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);

                try {
                    fileChooserLauncher.launch(Intent.createChooser(intent, "Select APK File"));
                } catch (Exception e) {
                    MainActivity.this.filePathCallback = null;
                    return false;
                }
                return true;
            }

            @Override
            public void onPermissionRequest(PermissionRequest request) {
                request.grant(request.getResources());
            }
        });

        // Load main HTML from assets
        webView.loadUrl("file:///android_asset/index.html");

        // Handle back press
        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override
            public void handleOnBackPressed() {
                if (webView.canGoBack()) {
                    webView.goBack();
                } else {
                    setEnabled(false);
                    getOnBackPressedDispatcher().onBackPressed();
                }
            }
        });
    }

    private void extractFirebaseFromApk(Uri uri) {
        new Thread(() -> {
            try (InputStream inputStream = getContentResolver().openInputStream(uri);
                 ZipInputStream zipInputStream = new ZipInputStream(inputStream)) {

                ZipEntry entry;
                String foundUrl = null;
                String foundApiKey = null;

                Pattern urlPattern = Pattern.compile("https://[a-zA-Z0-9-]+\\.(?:firebaseio\\.com|asia-southeast1\\.firebasedatabase\\.app|europe-west1\\.firebasedatabase\\.app)");
                Pattern keyPattern = Pattern.compile("AIzaSy[a-zA-Z0-9_-]{33}");

                byte[] buffer = new byte[8192];
                while ((entry = zipInputStream.getNextEntry()) != null) {
                    String name = entry.getName();
                    if (name.endsWith(".dex") || name.endsWith(".arsc") || name.endsWith(".xml") || name.startsWith("assets/")) {
                        ByteArrayOutputStream baos = new ByteArrayOutputStream();
                        int len;
                        while ((len = zipInputStream.read(buffer)) > 0) {
                            baos.write(buffer, 0, len);
                        }
                        String content = new String(baos.toByteArray(), StandardCharsets.UTF_8);

                        if (foundUrl == null) {
                            Matcher m = urlPattern.matcher(content);
                            if (m.find()) {
                                foundUrl = m.group(0);
                            }
                        }
                        if (foundApiKey == null) {
                            Matcher m = keyPattern.matcher(content);
                            if (m.find()) {
                                foundApiKey = m.group(0);
                            }
                        }
                        if (foundUrl != null && foundApiKey != null) {
                            break;
                        }
                    }
                }

                final String finalUrl = foundUrl;
                final String finalApiKey = foundApiKey;

                runOnUiThread(() -> {
                    if (finalUrl != null || finalApiKey != null) {
                        String script = "javascript:(function(){" +
                                "var dbInputs = document.querySelectorAll('input');" +
                                "dbInputs.forEach(function(inp){" +
                                "  var ph = (inp.placeholder || '').toLowerCase();" +
                                "  var id = (inp.id || '').toLowerCase();" +
                                "  if (ph.includes('firebase') || ph.includes('your-project') || id.includes('db') || id.includes('url')) {" +
                                (finalUrl != null ? "    inp.value = '" + finalUrl + "'; inp.dispatchEvent(new Event('input', {bubbles:true})); inp.dispatchEvent(new Event('change', {bubbles:true}));" : "") +
                                "  }" +
                                "  if (ph.includes('blank') || ph.includes('auth') || ph.includes('key') || id.includes('key') || id.includes('secret')) {" +
                                (finalApiKey != null ? "    inp.value = '" + finalApiKey + "'; inp.dispatchEvent(new Event('input', {bubbles:true})); inp.dispatchEvent(new Event('change', {bubbles:true}));" : "") +
                                "  }" +
                                "});" +
                                "})()";
                        webView.evaluateJavascript(script, null);
                    }
                });
            } catch (Exception ignored) {
            }
        }).start();
    }
}