// Camera barcode scanning for the Nutrition page.
// Progressive enhancement: without this script (or a camera) the user types the barcode instead.
// Uses the browser's built-in BarcodeDetector where available (Chrome on Android, Edge), and otherwise
// loads the ZXing decoder from a CDN, only when the user taps "Scan" (Safari, Firefox).
(() => {
  const form = document.querySelector("[data-barcode-form]");
  const dialog = document.querySelector("[data-scanner]");
  if (!form || !dialog) return;

  const ZXING_URL = "https://cdn.jsdelivr.net/npm/@zxing/browser@0.2.1/+esm";
  const FORMATS = ["ean_13", "ean_8", "upc_a", "upc_e"];

  const startButton = form.querySelector("[data-scan-start]");
  const input = form.querySelector("#barcode");
  const video = dialog.querySelector("[data-scan-video]");
  const status = dialog.querySelector("[data-scan-status]");
  const errorBox = document.querySelector("[data-scan-error]");

  // Browsers only allow camera access on HTTPS pages (or localhost).
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia || !dialog.showModal) return;
  startButton.hidden = false;

  let stream = null;
  let stopDecoding = null;
  let session = 0; // bumped on every stop, so a scan that is still starting up knows it was cancelled

  function showError(message) {
    errorBox.textContent = message;
    errorBox.hidden = false;
  }

  function stop() {
    session += 1;
    stopDecoding?.();
    stopDecoding = null;
    stream?.getTracks().forEach((track) => track.stop());
    stream = null;
    video.srcObject = null;
    if (dialog.open) dialog.close();
  }

  function found(code) {
    stop();
    input.value = code;
    form.requestSubmit ? form.requestSubmit() : form.submit();
  }

  async function nativeDetector() {
    if (!("BarcodeDetector" in window)) return null;
    try {
      const supported = await window.BarcodeDetector.getSupportedFormats();
      const formats = FORMATS.filter((format) => supported.includes(format));
      return formats.length ? new window.BarcodeDetector({ formats }) : null;
    } catch {
      return null;
    }
  }

  function scanWithDetector(detector, current) {
    const tick = async () => {
      if (current !== session) return;
      if (video.readyState >= video.HAVE_CURRENT_DATA) {
        try {
          const codes = await detector.detect(video);
          if (codes.length && current === session) return found(codes[0].rawValue);
        } catch {
          // A frame that can't be read yet; try the next one.
        }
      }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }

  async function scanWithZxing(current) {
    const { BrowserMultiFormatOneDReader } = await import(ZXING_URL);
    if (current !== session) return;
    const reader = new BrowserMultiFormatOneDReader();
    const controls = await reader.decodeFromStream(stream, video, (result) => {
      if (result && current === session) found(result.getText());
    });
    if (current !== session) controls.stop();
    else stopDecoding = () => controls.stop();
  }

  function cameraError(error) {
    if (error?.name === "NotAllowedError") return "Camera access was blocked. Allow it in your browser settings, or type the barcode instead.";
    if (error?.name === "NotFoundError" || error?.name === "OverconstrainedError") return "No camera found. Type the barcode instead.";
    return "Couldn't start the camera. Type the barcode instead.";
  }

  async function start() {
    errorBox.hidden = true;
    const current = ++session;
    status.textContent = "Starting camera…";
    dialog.showModal();

    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" } }, audio: false });
    } catch (error) {
      if (current === session) {
        stop();
        showError(cameraError(error));
      }
      return;
    }
    if (current !== session) {
      stream.getTracks().forEach((track) => track.stop());
      return;
    }

    video.srcObject = stream;
    try {
      await video.play();
      status.textContent = "Hold the barcode inside the frame. It scans automatically.";
      const detector = await nativeDetector();
      if (detector) scanWithDetector(detector, current);
      else await scanWithZxing(current);
    } catch {
      if (current === session) {
        stop();
        showError("Scanning isn't supported in this browser. Type the barcode instead.");
      }
    }
  }

  startButton.addEventListener("click", start);
  dialog.querySelector("[data-scan-stop]").addEventListener("click", stop);
  dialog.addEventListener("cancel", stop); // Esc key
})();
