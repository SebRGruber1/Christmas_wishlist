// Decides how each wishlist picture sits in its square frame.
//
// - A photo with its own background (a shirt on grey, a product on cream)
//   fills the frame edge to edge.
// - A cut-out on white, or a very tall or wide picture, is shown whole.
//
// To tell them apart we look at the picture's border pixels. That needs the
// image host to allow it; when it doesn't, we reload the picture normally and
// decide from its shape alone.
(function () {
  function borderIsBlank(img) {
    var n = 24, c = document.createElement('canvas');
    c.width = c.height = n;
    var ctx = c.getContext('2d');
    ctx.drawImage(img, 0, 0, n, n);
    var d = ctx.getImageData(0, 0, n, n).data, blank = 0, total = 0;
    for (var y = 0; y < n; y++) {
      for (var x = 0; x < n; x++) {
        if (x > 0 && x < n - 1 && y > 0 && y < n - 1) continue;
        var i = (y * n + x) * 4;
        total++;
        if (d[i + 3] < 16 || (d[i] > 248 && d[i + 1] > 248 && d[i + 2] > 248)) blank++;
      }
    }
    return blank / total > 0.85;
  }

  function decide(img) {
    var ratio = img.naturalWidth / img.naturalHeight;
    var extreme = ratio > 1.7 || ratio < 0.6;
    var cover = !extreme;
    if (cover) {
      try {
        cover = !borderIsBlank(img);
      } catch (e) {
        // Host disallows reading pixels: only fill the frame when the picture
        // is close to square, so little is lost if we guessed wrong.
        cover = ratio > 0.8 && ratio < 1.25;
      }
    }
    img.classList.toggle('is-cover', cover);
    img.classList.add('is-ready');
  }

  function failed(img) {
    if (img.hasAttribute('crossorigin')) {
      // The host refused the pixel-readable request; load it the ordinary way.
      var src = img.getAttribute('src');
      img.removeAttribute('crossorigin');
      img.src = src;
    } else if (!img.dataset.usedPlaceholder) {
      img.dataset.usedPlaceholder = '1';
      img.src = img.dataset.placeholder;
    } else {
      img.classList.add('is-ready');
    }
  }

  document.querySelectorAll('img.wish-img').forEach(function (img) {
    img.addEventListener('load', function () { decide(img); });
    img.addEventListener('error', function () { failed(img); });
    if (img.complete) {
      if (img.naturalWidth > 0) decide(img); else failed(img);
    }
  });
})();
