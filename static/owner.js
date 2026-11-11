// Behaviour for the owner's editing page: share link, the bookmarks-bar
// button, and the picture part of the Add Item form.
(function () {
  var origin = window.location.origin;

  // ---------------------------------------------------------- share link
  var copyBtn = document.getElementById('copyShare');
  copyBtn.addEventListener('click', function () {
    var url = origin + '/public';
    navigator.clipboard.writeText(url).then(function () {
      copyBtn.textContent = 'Link copied';
      setTimeout(function () { copyBtn.textContent = 'Copy link to share'; }, 2000);
    }, function () {
      window.prompt('Copy this link:', url);
    });
  });

  // ------------------------------------------------- bookmarks-bar button
  // This small script runs on the shop's page when the bookmark is clicked.
  // It reads the product's name and main picture from that page and opens
  // this page with them filled in. Nothing is sent anywhere else.
  function onShopPage(ORIGIN) {
    var d = document;
    function meta(sel) { var e = d.querySelector(sel); return (e && e.content) || ''; }
    var img = '', brand = '', pname = '';
    // 1. Structured product data, when the shop provides it
    [].forEach.call(d.querySelectorAll('script[type="application/ld+json"]'), function (s) {
      try {
        var j = JSON.parse(s.textContent), list = [].concat(j['@graph'] || j);
        list.forEach(function (o) {
          if (!o || [].concat(o['@type']).indexOf('Product') < 0) return;
          var i = [].concat(o.image || [])[0];
          if (!img && i) img = i.url || i;
          if (!pname && typeof o.name === 'string') pname = o.name;
          if (!brand && o.brand) brand = o.brand.name || (typeof o.brand === 'string' ? o.brand : '');
        });
      } catch (e) {}
    });
    // 2. The picture the page offers for link previews
    img = img || meta('meta[property="og:image:secure_url"]') || meta('meta[property="og:image"]') || meta('meta[name="twitter:image"]');
    // 3. Otherwise the biggest picture on the page
    if (!img) {
      var best = 0;
      [].forEach.call(d.images, function (i) {
        var a = i.naturalWidth * i.naturalHeight;
        if (a > best) { best = a; img = i.currentSrc || i.src; }
      });
    }
    try { img = new URL(img, location.href).href; } catch (e) { img = ''; }
    var site = meta('meta[property="og:site_name"]') || location.hostname.replace(/^www\./, '');
    // Page titles look like "Brand | Product | Shop": keep the longest part.
    var name = (pname || meta('meta[property="og:title"]') || d.title).split(/ [|–—:] /)
      .sort(function (a, b) { return b.length - a.length; })[0];
    name = name.trim();
    var q = '?add=1&name=' + encodeURIComponent(name) + '&brand=' + encodeURIComponent(brand || site) +
            '&link=' + encodeURIComponent(location.href) + '&image=' + encodeURIComponent(img);
    window.open(ORIGIN + '/' + q, '_blank');
  }
  var bm = document.getElementById('bookmarklet');
  var code = '(' + onShopPage.toString().replace(/\s*\/\/[^\n]*\n/g, '\n').replace(/\s+/g, ' ') +
             ')(' + JSON.stringify(origin) + ');';
  bm.href = 'javascript:' + encodeURIComponent(code);
  bm.addEventListener('click', function (e) {
    e.preventDefault();
    alert("Don't click this here. Drag it up to your bookmarks bar, then click it while you're on a product page.");
  });

  // -------------------------------------------------------- picture field
  var form = document.getElementById('addForm');
  var fileInput = document.getElementById('image_file');
  var urlInput = document.getElementById('image_url_modal');
  var drop = document.getElementById('picDrop');
  var preview = document.getElementById('picPreview');
  var empty = document.getElementById('picEmpty');
  var status = document.getElementById('picStatus');
  var clearBtn = document.getElementById('picClear');
  var MAX_SIDE = 1400;

  function show(src, message, ok) {
    preview.hidden = !src;
    empty.hidden = !!src;
    clearBtn.hidden = !src;
    if (src) preview.src = src;
    status.textContent = message || '';
    status.className = 'small mt-1 ' + (ok === false ? 'text-danger' : 'text-muted');
  }

  function setFile(file) {
    var dt = new DataTransfer();
    if (file) dt.items.add(file);
    fileInput.files = dt.files;
  }

  // Shrink big photos in the browser before uploading: faster to send and
  // faster for visitors to load.
  function usePhoto(file) {
    if (!file || file.type.indexOf('image/') !== 0) {
      show('', "That file isn't a picture.", false);
      return;
    }
    var objectUrl = URL.createObjectURL(file);
    var img = new Image();
    img.onload = function () {
      var scale = Math.min(1, MAX_SIDE / Math.max(img.naturalWidth, img.naturalHeight));
      var c = document.createElement('canvas');
      c.width = Math.round(img.naturalWidth * scale);
      c.height = Math.round(img.naturalHeight * scale);
      var ctx = c.getContext('2d');
      ctx.fillStyle = '#fff';
      ctx.fillRect(0, 0, c.width, c.height);
      ctx.drawImage(img, 0, 0, c.width, c.height);
      c.toBlob(function (blob) {
        URL.revokeObjectURL(objectUrl);
        setFile(new File([blob], 'photo.jpg', { type: 'image/jpeg' }));
        urlInput.value = '';
        show(URL.createObjectURL(blob), 'Photo ready (' + Math.round(blob.size / 1024) + ' KB).');
      }, 'image/jpeg', 0.86);
    };
    img.onerror = function () {
      URL.revokeObjectURL(objectUrl);
      setFile(null);
      show('', "This browser can't read that picture. Try a JPG or PNG, or a screenshot.", false);
    };
    img.src = objectUrl;
  }

  function useAddress() {
    var url = urlInput.value.trim();
    if (!url) { if (!fileInput.files.length) show(''); return; }
    setFile(null);
    var probe = new Image();
    probe.referrerPolicy = 'no-referrer';
    probe.onload = function () { show(url, 'Picture found.'); };
    probe.onerror = function () {
      show('', "That address doesn't load as a picture. Use the picture's own address (right-click the picture, Copy image address), or upload a photo instead.", false);
    };
    probe.src = url;
  }

  fileInput.addEventListener('change', function () { if (fileInput.files[0]) usePhoto(fileInput.files[0]); });
  urlInput.addEventListener('change', useAddress);
  urlInput.addEventListener('paste', function () { setTimeout(useAddress, 0); });
  clearBtn.addEventListener('click', function () { setFile(null); urlInput.value = ''; show(''); });

  ['dragenter', 'dragover'].forEach(function (t) {
    drop.addEventListener(t, function (e) { e.preventDefault(); drop.classList.add('is-over'); });
  });
  ['dragleave', 'drop'].forEach(function (t) {
    drop.addEventListener(t, function (e) { e.preventDefault(); drop.classList.remove('is-over'); });
  });
  drop.addEventListener('drop', function (e) {
    var f = e.dataTransfer.files[0];
    if (f) { usePhoto(f); return; }
    var dropped = e.dataTransfer.getData('text/uri-list') || e.dataTransfer.getData('text/plain');
    if (dropped) { urlInput.value = dropped.split('\n')[0]; useAddress(); }
  });
  // Paste a copied picture (or a screenshot) anywhere in the form
  form.addEventListener('paste', function (e) {
    var items = (e.clipboardData && e.clipboardData.items) || [];
    for (var i = 0; i < items.length; i++) {
      if (items[i].type.indexOf('image/') === 0) {
        e.preventDefault();
        usePhoto(items[i].getAsFile());
        return;
      }
    }
  });

  // ---------------------------------- arriving from the bookmarks-bar button
  var params = new URLSearchParams(window.location.search);
  if (params.get('add')) {
    document.getElementById('name_modal').value = params.get('name') || '';
    document.getElementById('brand').value = params.get('brand') || '';
    document.getElementById('link_modal').value = params.get('link') || '';
    urlInput.value = params.get('image') || '';
    useAddress();
    history.replaceState(null, '', window.location.pathname);
    window.jQuery('#addItemModal').modal('show');
  }
})();
