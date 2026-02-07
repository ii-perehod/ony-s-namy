import React, { useState, useEffect, useRef, useCallback } from "react";

const API = "/api";

export default function App() {
  const [status, setStatus] = useState(null);
  const [mode, setMode] = useState("single"); // "single" | "batch" | "multi"
  const [processing, setProcessing] = useState(false);
  const [result, setResult] = useState(null);
  const [batchResults, setBatchResults] = useState(null);
  const [originalUrl, setOriginalUrl] = useState(null);
  const [error, setError] = useState(null);
  const [dragover, setDragover] = useState(false);
  const [multiFiles, setMultiFiles] = useState([null, null]);
  const [multiPreviews, setMultiPreviews] = useState([null, null]);
  const [batchFiles, setBatchFiles] = useState([]);
  const [batchPreviews, setBatchPreviews] = useState([]);
  const [batchProgress, setBatchProgress] = useState(null);
  const fileInputRef = useRef(null);
  const batchInputRef = useRef(null);
  const cameraInputRef = useRef(null);
  const multiInputRefs = [useRef(null), useRef(null)];

  const refreshStatus = useCallback(() => {
    fetch(`${API}/status`, { credentials: "include" })
      .then((r) => r.json())
      .then(setStatus)
      .catch((err) => console.error("Ошибка загрузки статуса:", err));
  }, []);

  useEffect(() => {
    refreshStatus();
  }, [refreshStatus]);

  // ── Single photo upload ───────────────────────────────────────────

  const handleFile = useCallback(
    async (file) => {
      if (!file || !file.type.startsWith("image/")) {
        setError("Пожалуйста, выберите изображение (JPG, PNG, WEBP).");
        return;
      }
      if (status && status.remaining <= 0) {
        setError("Лимит исчерпан. Купите дополнительный пакет или оформите подписку.");
        return;
      }

      setError(null);
      setResult(null);
      setBatchResults(null);
      setProcessing(true);
      if (originalUrl) URL.revokeObjectURL(originalUrl);
      setOriginalUrl(URL.createObjectURL(file));

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

  // ── Multi photo upload (2 angles) ─────────────────────────────────

  const handleMultiFile = (index, file) => {
    if (!file || !file.type.startsWith("image/")) return;
    const newFiles = [...multiFiles];
    const newPreviews = [...multiPreviews];
    if (newPreviews[index]) URL.revokeObjectURL(newPreviews[index]);
    newFiles[index] = file;
    newPreviews[index] = URL.createObjectURL(file);
    setMultiFiles(newFiles);
    setMultiPreviews(newPreviews);
    setError(null);
  };

  const submitMulti = useCallback(async () => {
    if (!multiFiles[0] || !multiFiles[1]) {
      setError("Загрузите оба фото — с разных углов.");
      return;
    }
    if (status && status.remaining <= 0) {
      setError("Лимит исчерпан. Купите дополнительный пакет или оформите подписку.");
      return;
    }

    setError(null);
    setResult(null);
    setBatchResults(null);
    setProcessing(true);
    setOriginalUrl(multiPreviews[0]);

    const form = new FormData();
    form.append("files", multiFiles[0]);
    form.append("files", multiFiles[1]);

    try {
      const res = await fetch(`${API}/restore-multi`, {
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
  }, [multiFiles, multiPreviews, status]);

  // ── Batch upload ──────────────────────────────────────────────────

  const handleBatchFiles = (fileList) => {
    const valid = Array.from(fileList).filter((f) => f.type.startsWith("image/"));
    if (valid.length === 0) {
      setError("Не найдено изображений среди выбранных файлов.");
      return;
    }
    if (valid.length > 20) {
      setError("Максимум 20 фото за раз.");
      return;
    }
    batchPreviews.forEach((url) => URL.revokeObjectURL(url));
    setBatchFiles(valid);
    setBatchPreviews(valid.map((f) => URL.createObjectURL(f)));
    setError(null);
  };

  const removeBatchFile = (index) => {
    if (batchPreviews[index]) URL.revokeObjectURL(batchPreviews[index]);
    const newFiles = batchFiles.filter((_, i) => i !== index);
    const newPreviews = batchPreviews.filter((_, i) => i !== index);
    setBatchFiles(newFiles);
    setBatchPreviews(newPreviews);
  };

  const submitBatch = useCallback(async () => {
    if (batchFiles.length === 0) {
      setError("Добавьте хотя бы одно фото.");
      return;
    }
    if (status && status.remaining < batchFiles.length) {
      setError(`Недостаточно лимита. Осталось ${status.remaining}, выбрано ${batchFiles.length}.`);
      return;
    }

    setError(null);
    setResult(null);
    setBatchResults(null);
    setProcessing(true);
    setBatchProgress({ total: batchFiles.length, done: 0 });

    const form = new FormData();
    batchFiles.forEach((file) => form.append("files", file));

    try {
      const res = await fetch(`${API}/restore-batch`, {
        method: "POST",
        body: form,
        credentials: "include",
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Ошибка сервера (${res.status})`);
      }
      const data = await res.json();
      setBatchResults(data.results);
      setStatus((prev) => {
        if (!prev) return prev;
        const successCount = data.results.filter((r) => r.photo_id).length;
        return { ...prev, remaining: data.remaining, used: prev.used + successCount };
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setProcessing(false);
      setBatchProgress(null);
    }
  }, [batchFiles, status]);

  // ── Common ────────────────────────────────────────────────────────

  const onFileSelect = (e) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  };

  const onCameraCapture = (e) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  };

  const onBatchSelect = (e) => {
    if (e.target.files?.length) handleBatchFiles(e.target.files);
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDragover(false);
    if (mode === "batch") {
      if (e.dataTransfer.files?.length) handleBatchFiles(e.dataTransfer.files);
    } else {
      const file = e.dataTransfer.files?.[0];
      if (file) handleFile(file);
    }
  };

  const reset = () => {
    if (originalUrl) URL.revokeObjectURL(originalUrl);
    multiPreviews.forEach((url) => { if (url) URL.revokeObjectURL(url); });
    batchPreviews.forEach((url) => URL.revokeObjectURL(url));
    setResult(null);
    setBatchResults(null);
    setOriginalUrl(null);
    setError(null);
    setMultiFiles([null, null]);
    setMultiPreviews([null, null]);
    setBatchFiles([]);
    setBatchPreviews([]);
    setBatchProgress(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
    if (batchInputRef.current) batchInputRef.current.value = "";
    if (cameraInputRef.current) cameraInputRef.current.value = "";
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
              {status.remaining >= 999999 ? "безлимит" : `${status.remaining} фото`}
            </span>
          </span>
          <span>Обработано: {status.used}</span>
          {status.subscription && (
            <span className="sub-badge">
              Подписка: {status.subscription === "sub_unlimited" ? "безлимит" : `${status.sub_photo_limit} фото/мес`}
            </span>
          )}
        </div>
      )}

      {/* Mode selector — only show when not processing/showing result */}
      {!processing && !result && !batchResults && (
        <>
          <div className="mode-selector">
            <button
              className={`mode-btn ${mode === "single" ? "active" : ""}`}
              onClick={() => { setMode("single"); setError(null); }}
            >
              <span className="mode-icon">1</span>
              Одно фото
            </button>
            <button
              className={`mode-btn ${mode === "batch" ? "active" : ""}`}
              onClick={() => { setMode("batch"); setError(null); }}
            >
              <span className="mode-icon">+</span>
              Несколько фото
            </button>
            <button
              className={`mode-btn ${mode === "multi" ? "active" : ""}`}
              onClick={() => { setMode("multi"); setError(null); }}
            >
              <span className="mode-icon">2</span>
              Без бликов
            </button>
          </div>

          {/* Tips */}
          {mode === "single" && <Tips mode="single" />}
          {mode === "batch" && <Tips mode="batch" />}
          {mode === "multi" && <Tips mode="multi" />}

          {/* Single upload */}
          {mode === "single" && (
            <>
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
                  {exhausted ? "Лимит исчерпан" : "Загрузите старое фото"}
                </h2>
                <p>
                  {exhausted
                    ? "Купите пакет или оформите подписку, чтобы продолжить"
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
              {/* Camera button */}
              {!exhausted && (
                <button
                  className="btn btn-camera"
                  onClick={() => cameraInputRef.current?.click()}
                >
                  Снять фото с камеры
                  <input
                    ref={cameraInputRef}
                    type="file"
                    accept="image/*"
                    capture="environment"
                    onChange={onCameraCapture}
                  />
                </button>
              )}
            </>
          )}

          {/* Batch upload */}
          {mode === "batch" && (
            <div className="batch-upload">
              <div
                className={`upload-area ${dragover ? "dragover" : ""} ${
                  exhausted ? "disabled" : ""
                }`}
                onClick={() => !exhausted && batchInputRef.current?.click()}
                onDragOver={(e) => {
                  e.preventDefault();
                  if (!exhausted) setDragover(true);
                }}
                onDragLeave={() => setDragover(false)}
                onDrop={exhausted ? (e) => e.preventDefault() : onDrop}
              >
                <span className="upload-icon">📁</span>
                <h2>
                  {exhausted ? "Лимит исчерпан" : "Загрузите несколько фото"}
                </h2>
                <p>
                  {exhausted
                    ? "Купите пакет или оформите подписку, чтобы продолжить"
                    : "Выберите до 20 фото за раз"}
                </p>
                <p>JPG, PNG, WEBP — до 20 МБ каждое</p>
                <input
                  ref={batchInputRef}
                  type="file"
                  accept="image/*"
                  multiple
                  onChange={onBatchSelect}
                />
              </div>

              {batchPreviews.length > 0 && (
                <div className="batch-previews">
                  <div className="batch-count">
                    Выбрано: {batchFiles.length} фото
                  </div>
                  <div className="batch-grid">
                    {batchPreviews.map((url, i) => (
                      <div key={i} className="batch-thumb">
                        <img src={url} alt={batchFiles[i]?.name} />
                        <button
                          className="batch-remove"
                          onClick={() => removeBatchFile(i)}
                        >
                          ×
                        </button>
                      </div>
                    ))}
                  </div>
                  {!exhausted && (
                    <button className="btn btn-primary" onClick={submitBatch}>
                      Восстановить все ({batchFiles.length} фото)
                    </button>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Multi upload */}
          {mode === "multi" && (
            <div className="multi-upload">
              {[0, 1].map((i) => (
                <div
                  key={i}
                  className={`upload-slot ${multiPreviews[i] ? "has-preview" : ""} ${
                    exhausted ? "disabled" : ""
                  }`}
                  onClick={() => !exhausted && multiInputRefs[i].current?.click()}
                >
                  {multiPreviews[i] ? (
                    <img src={multiPreviews[i]} alt={`Ракурс ${i + 1}`} />
                  ) : (
                    <>
                      <span className="slot-number">{i + 1}</span>
                      <span className="slot-label">
                        {i === 0 ? "Первый ракурс" : "Второй ракурс"}
                      </span>
                    </>
                  )}
                  <input
                    ref={multiInputRefs[i]}
                    type="file"
                    accept="image/*"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) handleMultiFile(i, file);
                    }}
                  />
                </div>
              ))}
              {multiFiles[0] && multiFiles[1] && !exhausted && (
                <button className="btn btn-primary btn-merge" onClick={submitMulti}>
                  Объединить и восстановить
                </button>
              )}
            </div>
          )}
        </>
      )}

      {/* Processing */}
      {processing && (
        <div className="processing">
          <div className="spinner" />
          <p>
            {mode === "batch"
              ? `Обрабатываем ${batchFiles.length} фото...`
              : mode === "multi"
              ? "Объединяем ракурсы, убираем блики, восстанавливаем..."
              : "Восстанавливаем и раскрашиваем ваше фото..."}
          </p>
          <p style={{ fontSize: "0.8rem", color: "#666", marginTop: 8 }}>
            {mode === "batch"
              ? "Каждое фото обрабатывается 30–90 секунд"
              : "Обычно это занимает 30–90 секунд"}
          </p>
          <ProcessingSteps mode={mode} />
        </div>
      )}

      {/* Single result */}
      {result && originalUrl && !batchResults && (
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

      {/* Batch results */}
      {batchResults && (
        <div className="result">
          <h3 style={{ textAlign: "center", marginBottom: 16 }}>
            Готово! Обработано: {batchResults.filter((r) => r.photo_id).length} из {batchResults.length}
          </h3>
          <div className="batch-results-grid">
            {batchResults.map((r, i) => (
              <div key={i} className="batch-result-card">
                {r.photo_id ? (
                  <>
                    <img src={`${API}/download/${r.photo_id}`} alt={r.filename || "Результат"} />
                    <a
                      href={`${API}/download/${r.photo_id}`}
                      download
                      className="btn btn-primary btn-sm"
                    >
                      Скачать
                    </a>
                  </>
                ) : (
                  <div className="batch-result-error">{r.error}</div>
                )}
              </div>
            ))}
          </div>
          <div className="actions" style={{ marginTop: 16 }}>
            <button className="btn btn-secondary" onClick={reset}>
              Загрузить ещё
            </button>
          </div>
        </div>
      )}

      {/* Error */}
      {error && <div className="error">{error}</div>}

      {/* Payment section */}
      {exhausted && <PaymentSection onSubscribed={refreshStatus} />}

      <footer>
        ФотоРеставратор — восстановление старых фото с помощью ИИ.
        <br />
        Черты лица, обстановка и детали сохраняются без изменений.
      </footer>
    </div>
  );
}

/* ── Tips ─────────────────────────────────────────────────────────── */

function Tips({ mode }) {
  if (mode === "multi") {
    return (
      <div className="tips">
        <div className="tips-title">Как убрать блики</div>
        <div className="tips-grid">
          <div className="tip">
            <span className="tip-num">1</span>
            <span>Сфотографируйте старое фото под одним углом</span>
          </div>
          <div className="tip">
            <span className="tip-num">2</span>
            <span>Сфотографируйте то же фото под другим углом, чтобы блик сместился</span>
          </div>
          <div className="tip">
            <span className="tip-num">3</span>
            <span>Загрузите оба снимка — система сама уберёт блики и склеит лучшее из обоих</span>
          </div>
        </div>
      </div>
    );
  }

  if (mode === "batch") {
    return (
      <div className="tips">
        <div className="tips-title">Пакетная обработка</div>
        <div className="tips-grid">
          <div className="tip">
            <span className="tip-num">1</span>
            <span>Выберите до 20 фотографий за раз</span>
          </div>
          <div className="tip">
            <span className="tip-num">2</span>
            <span>Все фото будут обработаны последовательно — вы получите результат для каждого</span>
          </div>
          <div className="tip">
            <span className="tip-num">3</span>
            <span>Удобно для целых альбомов — выберите папку и загрузите всё сразу</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="tips">
      <div className="tips-title">Советы для лучшего результата</div>
      <div className="tips-grid">
        <div className="tip">
          <span className="tip-num">1</span>
          <span>Сканируйте фото при 300+ dpi или фотографируйте при хорошем свете</span>
        </div>
        <div className="tip">
          <span className="tip-num">2</span>
          <span>Избегайте бликов — если не получается, используйте режим «Без бликов»</span>
        </div>
        <div className="tip">
          <span className="tip-num">3</span>
          <span>Фото из рамки можно не доставать — система сама обрежет края</span>
        </div>
      </div>
    </div>
  );
}

/* ── Processing Steps ────────────────────────────────────────────── */

function ProcessingSteps({ mode }) {
  const steps = mode === "multi"
    ? [
        "Совмещение двух ракурсов",
        "Удаление бликов и отражений",
        "Обрезка и выравнивание",
        "Восстановление лиц и деталей",
        "Колоризация",
      ]
    : mode === "batch"
    ? [
        "Обработка каждого фото по очереди",
        "Обрезка и выравнивание",
        "Удаление царапин",
        "Восстановление лиц и деталей",
        "Колоризация",
      ]
    : [
        "Обрезка и выравнивание",
        "Удаление царапин",
        "Улучшение контраста",
        "Восстановление лиц и деталей",
        "Колоризация",
      ];

  return (
    <div className="processing-steps">
      {steps.map((step, i) => (
        <div key={i} className="processing-step">
          <span className="step-dot" />
          <span>{step}</span>
        </div>
      ))}
    </div>
  );
}

/* ── Before/After Comparison Slider ──────────────────────────────── */

function ImageComparison({ originalUrl, resultUrl }) {
  const containerRef = useRef(null);
  const [sliderPos, setSliderPos] = useState(50);
  const [resultLoaded, setResultLoaded] = useState(false);
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
        <img
          src={resultUrl}
          alt="Результат"
          onLoad={() => setResultLoaded(true)}
        />

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

function PaymentSection({ onSubscribed }) {
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState("subscription"); // "subscription" | "packs"

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
    } catch (err) {
      console.error("Ошибка оплаты:", err);
      alert(
        "Оплата временно недоступна. Для настройки добавьте ключи ЮKassa в .env"
      );
    } finally {
      setLoading(false);
    }
  };

  const subscribe = async (planId) => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/subscribe`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan_id: planId }),
        credentials: "include",
      });
      const data = await res.json();
      if (data.checkout_url) {
        window.location.href = data.checkout_url;
      }
    } catch (err) {
      console.error("Ошибка подписки:", err);
      alert(
        "Подписка временно недоступна. Для настройки добавьте ключи ЮKassa в .env"
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="payment-section">
      <h3>Получить больше фото</h3>

      <div className="payment-tabs">
        <button
          className={`payment-tab ${tab === "subscription" ? "active" : ""}`}
          onClick={() => setTab("subscription")}
        >
          Подписка
        </button>
        <button
          className={`payment-tab ${tab === "packs" ? "active" : ""}`}
          onClick={() => setTab("packs")}
        >
          Разовый пакет
        </button>
      </div>

      {tab === "subscription" && (
        <>
          <p className="payment-hint">
            Ежемесячная подписка — лимит обновляется каждый месяц
          </p>
          <div className="packs">
            <div className="pack-card sub-card" onClick={() => !loading && subscribe("sub_30")} style={{ pointerEvents: loading ? 'none' : 'auto', opacity: loading ? 0.5 : 1 }}>
              <div className="count">30</div>
              <div className="label">фото/мес</div>
              <div className="sub-tag">подписка</div>
            </div>
            <div className="pack-card sub-card popular" onClick={() => !loading && subscribe("sub_100")} style={{ pointerEvents: loading ? 'none' : 'auto', opacity: loading ? 0.5 : 1 }}>
              <div className="popular-badge">Выгодно</div>
              <div className="count">100</div>
              <div className="label">фото/мес</div>
              <div className="sub-tag">подписка</div>
            </div>
            <div className="pack-card sub-card" onClick={() => !loading && subscribe("sub_unlimited")} style={{ pointerEvents: loading ? 'none' : 'auto', opacity: loading ? 0.5 : 1 }}>
              <div className="count">∞</div>
              <div className="label">безлимит</div>
              <div className="sub-tag">подписка</div>
            </div>
          </div>
        </>
      )}

      {tab === "packs" && (
        <>
          <p className="payment-hint">
            Разовая покупка — фото не сгорают, используйте в любое время
          </p>
          <div className="packs">
            <div className="pack-card" onClick={() => !loading && buyPack("pack_10")} style={{ pointerEvents: loading ? 'none' : 'auto', opacity: loading ? 0.5 : 1 }}>
              <div className="count">10</div>
              <div className="label">фото</div>
            </div>
            <div className="pack-card" onClick={() => !loading && buyPack("pack_50")} style={{ pointerEvents: loading ? 'none' : 'auto', opacity: loading ? 0.5 : 1 }}>
              <div className="count">50</div>
              <div className="label">фото</div>
            </div>
            <div className="pack-card" onClick={() => !loading && buyPack("pack_200")} style={{ pointerEvents: loading ? 'none' : 'auto', opacity: loading ? 0.5 : 1 }}>
              <div className="count">200</div>
              <div className="label">фото</div>
            </div>
          </div>
        </>
      )}

      {loading && (
        <p style={{ textAlign: "center", marginTop: 12, color: "#9999a8" }}>
          Переход к оплате...
        </p>
      )}
    </div>
  );
}
