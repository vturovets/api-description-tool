import { useEffect, useMemo, useRef, useState } from "react";

const MAX_UPLOAD_MB = 10;
const MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024;

const formatBytes = (bytes) => {
  if (!Number.isFinite(bytes)) {
    return "0 B";
  }
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(1)} ${units[unitIndex]}`;
};

const statusStyles = {
  idle: "bg-slate-800 text-slate-300 border-slate-700",
  uploading: "bg-amber-500/10 text-amber-200 border-amber-400/50",
  success: "bg-emerald-500/10 text-emerald-200 border-emerald-400/50",
  error: "bg-rose-500/10 text-rose-200 border-rose-400/50",
  running: "bg-sky-500/10 text-sky-200 border-sky-400/50",
};

const buildErrorMessage = async (response, fallback) => {
  if (!response) {
    return fallback;
  }
  try {
    const payload = await response.json();
    if (payload?.message) {
      return payload.message;
    }
  } catch (error) {
    return fallback;
  }
  return fallback;
};

export default function App() {
  const [health, setHealth] = useState({ version: "unknown", git_sha: "unknown" });
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploadInfo, setUploadInfo] = useState(null);
  const [uploadStatus, setUploadStatus] = useState("idle");
  const [uploadError, setUploadError] = useState("");
  const [selectedPath, setSelectedPath] = useState("");
  const [selectedMethod, setSelectedMethod] = useState("");
  const [format, setFormat] = useState("xlsx");
  const [validate, setValidate] = useState(false);
  const [jobId, setJobId] = useState("");
  const [jobStatus, setJobStatus] = useState("idle");
  const [jobLogs, setJobLogs] = useState([]);
  const [jobMetrics, setJobMetrics] = useState(null);
  const [rowCounts, setRowCounts] = useState(null);
  const [downloadUrl, setDownloadUrl] = useState("");
  const [convertStatus, setConvertStatus] = useState("idle");
  const [convertError, setConvertError] = useState("");
  const fileInputRef = useRef(null);

  const pathOptions = useMemo(() => {
    if (!uploadInfo?.paths) {
      return [];
    }
    return Object.keys(uploadInfo.paths).sort();
  }, [uploadInfo]);

  const methodOptions = useMemo(() => {
    if (!uploadInfo?.paths || !selectedPath) {
      return [];
    }
    return uploadInfo.paths[selectedPath] ?? [];
  }, [uploadInfo, selectedPath]);

  useEffect(() => {
    let active = true;
    fetch("/health")
      .then((response) => (response.ok ? response.json() : null))
      .then((payload) => {
        if (!active || !payload) {
          return;
        }
        setHealth(payload);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!uploadInfo) {
      setSelectedPath("");
      setSelectedMethod("");
      return;
    }
    if (pathOptions.length === 1) {
      setSelectedPath(pathOptions[0]);
    } else if (!pathOptions.includes(selectedPath)) {
      setSelectedPath("");
    }
  }, [pathOptions, uploadInfo, selectedPath]);

  useEffect(() => {
    if (!methodOptions.length) {
      setSelectedMethod("");
      return;
    }
    if (methodOptions.length === 1) {
      setSelectedMethod(methodOptions[0]);
      return;
    }
    if (!methodOptions.includes(selectedMethod)) {
      setSelectedMethod("");
    }
  }, [methodOptions, selectedMethod]);

  useEffect(() => {
    if (!jobId) {
      return undefined;
    }
    let cancelled = false;
    const poll = async () => {
      try {
        const response = await fetch(`/api/job/${jobId}`);
        if (!response.ok) {
          return;
        }
        const payload = await response.json();
        if (cancelled) {
          return;
        }
        setJobStatus(payload.status);
        setJobLogs(payload.logs ?? []);
        setJobMetrics(payload.metrics ?? null);
        setDownloadUrl(payload.download_url ?? "");
        if (payload.status === "succeeded") {
          setConvertStatus("success");
        } else if (payload.status === "failed") {
          setConvertStatus("error");
        }
      } catch (error) {
        if (!cancelled) {
          setConvertStatus("error");
        }
      }
    };
    poll();
    const interval = setInterval(poll, 2000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [jobId]);

  const resetConversionState = () => {
    setJobId("");
    setJobStatus("idle");
    setJobLogs([]);
    setJobMetrics(null);
    setRowCounts(null);
    setDownloadUrl("");
    setConvertStatus("idle");
    setConvertError("");
  };

  const handleFileSelection = (file) => {
    if (!file) {
      return;
    }
    resetConversionState();
    setUploadError("");
    if (file.size > MAX_UPLOAD_BYTES) {
      setUploadStatus("error");
      setUploadError(`File exceeds ${MAX_UPLOAD_MB} MB limit.`);
      setSelectedFile(file);
      return;
    }
    setSelectedFile(file);
    startUpload(file);
  };

  const startUpload = async (file) => {
    setUploadStatus("uploading");
    setUploadError("");
    setUploadInfo(null);
    const formData = new FormData();
    formData.append("file", file);
    const response = await fetch("/api/upload", {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      const message = await buildErrorMessage(response, "Upload failed.");
      setUploadStatus("error");
      setUploadError(message);
      return;
    }
    const payload = await response.json();
    setUploadInfo(payload);
    setUploadStatus("success");
  };

  const handleDrop = (event) => {
    event.preventDefault();
    const file = event.dataTransfer.files?.[0];
    handleFileSelection(file);
  };

  const handleConvert = async () => {
    if (!uploadInfo) {
      return;
    }
    const methodRequired = methodOptions.length > 1;
    const methodValue = methodRequired ? selectedMethod : methodOptions[0] ?? "";
    setConvertStatus("running");
    setConvertError("");
    setRowCounts(null);
    setJobLogs([]);
    const payload = {
      upload_id: uploadInfo.upload_id,
      path: selectedPath,
      format,
      validate,
    };
    if (methodValue) {
      payload.method = methodValue;
    }
    const response = await fetch("/api/convert", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const message = await buildErrorMessage(response, "Conversion failed.");
      setConvertStatus("error");
      setConvertError(message);
      return;
    }
    const data = await response.json();
    setJobId(data.job_id);
    setJobStatus(data.status);
    setDownloadUrl(data.download_url);
    setRowCounts(data.rows);
  };

  const convertDisabled =
    uploadStatus !== "success" ||
    !selectedPath ||
    (methodOptions.length > 1 && !selectedMethod) ||
    convertStatus === "running";

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <main className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-6 py-10">
        <header className="space-y-3">
          <p className="text-xs uppercase tracking-[0.4em] text-slate-400">API Description Tool</p>
          <h1 className="text-3xl font-semibold text-white">OpenAPI → Tabular Description</h1>
          <p className="max-w-2xl text-sm text-slate-300">
            Upload your OpenAPI YAML, choose the path and method you want to document, and generate
            the tabular description in XLSX or CSV format.
          </p>
        </header>

        <section className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 shadow-lg">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold">1. Upload OpenAPI spec</h2>
                <p className="text-sm text-slate-400">
                  Drag and drop a YAML file (max {MAX_UPLOAD_MB} MB).
                </p>
              </div>
              <span
                className={`rounded-full border px-3 py-1 text-xs font-medium capitalize ${statusStyles[uploadStatus]}`}
              >
                {uploadStatus === "idle" ? "ready" : uploadStatus}
              </span>
            </div>

            <div
              className="mt-6 flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-slate-700 bg-slate-950/40 px-6 py-10 text-center transition hover:border-slate-500"
              onDragOver={(event) => event.preventDefault()}
              onDrop={handleDrop}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".yaml,.yml"
                className="hidden"
                onChange={(event) => handleFileSelection(event.target.files?.[0])}
              />
              <button
                type="button"
                className="rounded-full border border-slate-600 bg-slate-800 px-4 py-2 text-sm font-medium text-slate-100 transition hover:border-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
                onClick={() => fileInputRef.current?.click()}
              >
                Choose file
              </button>
              <p className="text-xs text-slate-400">or drop a file here</p>
            </div>

            <div className="mt-5 flex flex-col gap-2 text-sm">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-slate-300">
                  {selectedFile ? selectedFile.name : "No file selected"}
                </span>
                {selectedFile && <span className="text-xs text-slate-400">{formatBytes(selectedFile.size)}</span>}
              </div>
              {uploadError && (
                <div className="rounded-lg border border-rose-500/50 bg-rose-500/10 px-3 py-2 text-xs text-rose-100">
                  {uploadError}
                </div>
              )}
              {uploadStatus === "error" && selectedFile && (
                <button
                  type="button"
                  className="w-fit rounded-full border border-rose-400/60 px-3 py-1 text-xs font-semibold text-rose-100 transition hover:border-rose-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-400"
                  onClick={() => startUpload(selectedFile)}
                >
                  Retry upload
                </button>
              )}
              {uploadStatus === "success" && uploadInfo && (
                <p className="text-xs text-emerald-200">
                  Uploaded {uploadInfo.file_name} with {Object.keys(uploadInfo.paths).length} paths detected.
                </p>
              )}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 shadow-lg">
            <h2 className="text-lg font-semibold">2. Configure conversion</h2>
            <div className="mt-4 flex flex-col gap-4 text-sm">
              <label className="flex flex-col gap-2">
                <span className="text-slate-300">Path</span>
                <select
                  className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 disabled:cursor-not-allowed disabled:text-slate-500"
                  value={selectedPath}
                  onChange={(event) => setSelectedPath(event.target.value)}
                  disabled={!pathOptions.length}
                >
                  <option value="">Select a path</option>
                  {pathOptions.map((path) => (
                    <option key={path} value={path}>
                      {path}
                    </option>
                  ))}
                </select>
              </label>

              <label className="flex flex-col gap-2">
                <span className="text-slate-300">Method</span>
                <select
                  className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 disabled:cursor-not-allowed disabled:text-slate-500"
                  value={selectedMethod}
                  onChange={(event) => setSelectedMethod(event.target.value)}
                  disabled={!methodOptions.length || methodOptions.length === 1}
                  aria-required={methodOptions.length > 1}
                >
                  <option value="">
                    {methodOptions.length === 1 ? `Using ${methodOptions[0].toUpperCase()}` : "Select a method"}
                  </option>
                  {methodOptions.map((method) => (
                    <option key={method} value={method}>
                      {method.toUpperCase()}
                    </option>
                  ))}
                </select>
                {methodOptions.length > 1 && !selectedMethod && (
                  <span className="text-xs text-amber-200">Select a method to enable conversion.</span>
                )}
              </label>

              <div className="grid gap-3 sm:grid-cols-2">
                <label className="flex flex-col gap-2">
                  <span className="text-slate-300">Format</span>
                  <select
                    className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
                    value={format}
                    onChange={(event) => setFormat(event.target.value)}
                  >
                    <option value="xlsx">Excel (.xlsx)</option>
                    <option value="csv">CSV (.zip)</option>
                  </select>
                </label>
                <label className="flex items-center gap-3 rounded-lg border border-slate-700 bg-slate-950 px-3 py-3">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-slate-500 bg-slate-900 text-sky-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
                    checked={validate}
                    onChange={(event) => setValidate(event.target.checked)}
                  />
                  <span className="text-slate-300">Validate OpenAPI spec</span>
                </label>
              </div>

              <button
                type="button"
                className="mt-2 flex items-center justify-center gap-2 rounded-lg bg-sky-500 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-sky-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-300 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
                onClick={handleConvert}
                disabled={convertDisabled}
              >
                {convertStatus === "running" ? "Converting..." : "Convert"}
              </button>
              {convertError && (
                <div className="rounded-lg border border-rose-500/50 bg-rose-500/10 px-3 py-2 text-xs text-rose-100">
                  {convertError}
                </div>
              )}
            </div>
          </div>
        </section>

        <section className="grid gap-6 lg:grid-cols-[1fr_1fr]">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 shadow-lg">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">3. Conversion progress</h2>
              <span
                className={`rounded-full border px-3 py-1 text-xs font-medium capitalize ${
                  statusStyles[convertStatus] ?? statusStyles.idle
                }`}
              >
                {convertStatus === "idle" ? "waiting" : convertStatus}
              </span>
            </div>
            <div className="mt-4 space-y-4 text-sm text-slate-300">
              <div className="flex flex-col gap-2">
                <span>Status: {jobStatus === "idle" ? "No job yet" : jobStatus}</span>
                <progress
                  className="h-2 w-full overflow-hidden rounded-full accent-sky-500"
                  value={jobStatus === "running" ? 50 : jobStatus === "succeeded" ? 100 : 0}
                  max="100"
                  aria-label="Conversion progress"
                />
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-lg border border-slate-800 bg-slate-950 px-3 py-2">
                  <p className="text-xs text-slate-400">Params rows</p>
                  <p className="text-lg font-semibold text-white">
                    {jobMetrics?.rows?.params ?? rowCounts?.params ?? "--"}
                  </p>
                </div>
                <div className="rounded-lg border border-slate-800 bg-slate-950 px-3 py-2">
                  <p className="text-xs text-slate-400">Request rows</p>
                  <p className="text-lg font-semibold text-white">
                    {jobMetrics?.rows?.request_body ?? rowCounts?.request_body ?? "--"}
                  </p>
                </div>
                <div className="rounded-lg border border-slate-800 bg-slate-950 px-3 py-2">
                  <p className="text-xs text-slate-400">Response rows</p>
                  <p className="text-lg font-semibold text-white">
                    {jobMetrics?.rows?.response_body ?? rowCounts?.response_body ?? "--"}
                  </p>
                </div>
              </div>
              {jobMetrics && (
                <p className="text-xs text-slate-400">
                  Duration: {jobMetrics.duration_ms} ms · Validation:{" "}
                  {jobMetrics.validate_enabled ? "Enabled" : "Disabled"} · Format: {jobMetrics.format.toUpperCase()}
                </p>
              )}
              {downloadUrl && (
                <a
                  href={downloadUrl}
                  className="inline-flex items-center gap-2 rounded-lg bg-emerald-400 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-emerald-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-200"
                >
                  Download output
                </a>
              )}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 shadow-lg">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">Job logs</h2>
              {jobId && <span className="text-xs text-slate-400">Job ID: {jobId}</span>}
            </div>
            <div
              className="mt-4 h-64 overflow-y-auto rounded-lg border border-slate-800 bg-slate-950 px-4 py-3 text-xs text-slate-200"
              role="log"
              aria-live="polite"
              aria-relevant="additions text"
            >
              {jobLogs.length === 0 && (
                <p className="text-slate-500">Logs will appear here once conversion starts.</p>
              )}
              <ul className="space-y-2">
                {jobLogs.map((entry, index) => (
                  <li key={`${entry.timestamp}-${index}`} className="space-y-1">
                    <p className="text-[11px] uppercase tracking-wide text-slate-500">
                      {entry.timestamp} · {entry.level}
                    </p>
                    <p>{entry.message}</p>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-slate-800 bg-slate-950 px-6 py-4 text-xs text-slate-500">
        <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-2">
          <span>API Description Tool Web UI</span>
          <span>
            Version {health.version} · SHA {health.git_sha}
          </span>
        </div>
      </footer>
    </div>
  );
}
