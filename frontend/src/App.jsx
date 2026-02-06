import React, { useState, useEffect, useRef, useCallback } from "react";

const API = "/api";

export default function App() {
  const [status, setStatus] = useState(null);
  const [processing, setProcessing] = useState(false);
  const [result, setResult] = useState(null);
  const [originalUrl, setOriginalUrl] = useState(null);
  const [error, setError] = useState(null);
  const [dragover, setDragover] = useState(false);
  const fileInputRef = useRef(null);

  // Fetch user status on mount
  useEffect(() => {
    fetch(`${API}/status`, { credentials: "include" })
      .then((r) => r.json())
      .then(setStatus)
      .catch(() => {});
  }, []);

  const handleFile = useCallback(
    async (file) => {
      if (!file || !file.type.startsWith("image/")) {
        setError("Пожалуйста, выберите изображение (JPG, PNG, WEBP).");
        return;
      }

      if (status && status.remaining <= 0) {
        setError("Лимит исчерпан. Купите дополнительный пакет фото.");
        return;
      }

      setError(null);
      setResult(null);
      setProcessing(true);

      // Show original preview
      const objectUrl = URL.createObjectURL(file);
      setOriginalUrl(objectUrl);

      const form = new FormData();
      form.append("file", file);

      try {
        const res = await fetch(`${API}/restore`, {
          method: "POST",
          body: form,
          credentials: "include",
        });

        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(data.detail || `Ошибка сервера (${res.status})`);
        }

        const data = await res.json();
        setResult(data);
        setStatus((prev) =>
          prev ? { ...prev, remaining: data.remaining, used: prev.used + 1 } : prev
        );
      } catch (err) {
        setError(err.message);
      } finally {
        setProcessing(false);
      }
    },
    [status]
  );

  const onFileSelect = (e) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDragover(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  };

  const reset = () => {
    setResult(null);
    setOriginalUrl(null);
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const exhausted = status && status.remaining <= 0;

  return (
    <div className="app">
      <header>
        <h1>ФотоРеставратор</h1>
        <p>Восстановление и колоризация старых фотографий</p>
      </header>

      {/* Status bar */}
      {status && (
        <div className="status-bar">
          <span>
            Осталось:{" "}
            <span
              className={`remaining ${
                status.remaining === 0
                  ? "exhausted"
                  : status.remaining <= 1
                  ? "warning"
                  : ""
              }`}
            >
              {status.remaining} фото
            </span>
          </span>
          <span>Обработано: {status.used}</span>
        </div>
      )}

      {/* Upload area */}
      {!processing && !result && (
        <div
          className={`upload-area ${dragover ? "dragover" : ""} ${
            exhausted ? "disabled" : ""
          }`}
          onClick={() => !exhausted && fileInputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            if (!exhausted) setDragover(true);
          }}
          onDragLeave={() => setDragover(false)}
          onDrop={exhausted ? (e) => e.preventDefault() : onDrop}
        >
          <span className="upload-icon">📸</span>
          <h2>
            {exhausted
              ? "Лимит исчерпан"
              : "Загрузите старое фото"}
          </h2>
          <p>
            {exhausted
              ? "Купите дополнительный пакет, чтобы продолжить"
              : "Перетащите файл сюда или нажмите для выбора"}
          </p>
          <p>JPG, PNG, WEBP — до 20 МБ</p>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            onChange={onFileSelect}
          />
        </div>
      )}

      {/* Processing */}
      {processing && (
        <div className="processing">
          <div className="spinner" />
          <p>Восстанавливаем и раскрашиваем ваше фото...</p>
          <p style={{ fontSize: "0.8rem", color: "#666", marginTop: 8 }}>
            Обычно это занимает 30–90 секунд
          </p>
        </div>
      )}

      {/* Result */}
      {result && originalUrl && (
        <div className="result">
          <ImageComparison
            originalUrl={originalUrl}
            resultUrl={`${API}/download/${result.photo_id}`}
          />
          <div className="actions">
            <a
              href={`${API}/download/${result.photo_id}`}
              download
              className="btn btn-primary"
            >
              Скачать результат
            </a>
            <button className="btn btn-secondary" onClick={reset}>
              Загрузить ещё
            </button>
          </div>
        </div>
      )}

      {/* Error */}
      {error && <div className="error">{error}</div>}

      {/* Payment section */}
      {exhausted && <PaymentSection />}

      <footer>
        ФотоРеставратор — восстановление старых фото с помощью ИИ.
        <br />
        Черты лица, обстановка и детали сохраняются без изменений.
      </footer>
    </div>
  );
}

/* ── Before/After Comparison Slider ──────────────────────────────── */

function ImageComparison({ originalUrl, resultUrl }) {
  const containerRef = useRef(null);
  const [sliderPos, setSliderPos] = useState(50);
  const [resultLoaded, setResultLoaded] = useState(false);
  const [resultImgWidth, setResultImgWidth] = useState(0);
  const dragging = useRef(false);

  const updateSlider = useCallback((clientX) => {
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    const x = clientX - rect.left;
    const pct = Math.max(0, Math.min(100, (x / rect.width) * 100));
    setSliderPos(pct);
  }, []);

  const onPointerDown = (e) => {
    dragging.current = true;
    updateSlider(e.clientX);
    e.currentTarget.setPointerCapture(e.pointerId);
  };

  const onPointerMove = (e) => {
    if (dragging.current) updateSlider(e.clientX);
  };

  const onPointerUp = () => {
    dragging.current = false;
  };

  return (
    <div className="comparison">
      <div
        className="comparison-container"
        ref={containerRef}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
      >
        {/* Result (full width background) */}
        <img
          src={resultUrl}
          alt="Результат"
          onLoad={(e) => {
            setResultLoaded(true);
            setResultImgWidth(e.target.naturalWidth);
          }}
        />

        {/* Original (clipped by slider) */}
        {resultLoaded && (
          <div
            className="comparison-original"
            style={{ width: `${sliderPos}%` }}
          >
            <img
              src={originalUrl}
              alt="Оригинал"
              style={{
                width: containerRef.current
                  ? `${containerRef.current.offsetWidth}px`
                  : "100%",
              }}
            />
          </div>
        )}

        {/* Slider handle */}
        {resultLoaded && (
          <div
            className="comparison-slider"
            style={{ left: `${sliderPos}%` }}
          />
        )}
      </div>
      <div className="comparison-labels">
        <span>Оригинал</span>
        <span>Результат</span>
      </div>
    </div>
  );
}

/* ── Payment Section ─────────────────────────────────────────────── */

function PaymentSection() {
  const [loading, setLoading] = useState(false);

  const buyPack = async (packId) => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/checkout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pack_id: packId }),
        credentials: "include",
      });
      const data = await res.json();
      if (data.checkout_url) {
        window.location.href = data.checkout_url;
      }
    } catch {
      // Stripe not configured — show info
      alert(
        "Оплата временно недоступна. Для настройки добавьте ключи Stripe в .env"
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="payment-section">
      <h3>Купить дополнительные фото</h3>
      <div className="packs">
        <div className="pack-card" onClick={() => buyPack("pack_10")}>
          <div className="count">10</div>
          <div className="label">фото</div>
        </div>
        <div className="pack-card" onClick={() => buyPack("pack_50")}>
          <div className="count">50</div>
          <div className="label">фото</div>
        </div>
        <div className="pack-card" onClick={() => buyPack("pack_200")}>
          <div className="count">200</div>
          <div className="label">фото</div>
        </div>
      </div>
      {loading && (
        <p style={{ textAlign: "center", marginTop: 12, color: "#9999a8" }}>
          Переход к оплате...
        </p>
      )}
    </div>
  );
}
