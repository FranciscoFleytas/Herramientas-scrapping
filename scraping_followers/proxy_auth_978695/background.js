
    var config = {
        mode: "fixed_servers",
        rules: {
            singleProxy: {scheme: "http", host: "brd.superproxy.io", port: parseInt(33335)},
            bypassList: ["localhost"]
        }
    };
    chrome.proxy.settings.set({value: config, scope: "regular"}, function() {});
    function callbackFn(details) {
        return { authCredentials: { username: "brd-customer-hl_23e53168-zone-residential_proxy1-country-ar-session-978695", password: "ei0g975bijby" } };
    }
    chrome.webRequest.onAuthRequired.addListener(callbackFn, {urls: ["<all_urls>"]}, ['blocking']);
    