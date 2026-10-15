# Audio Transcription API

A lightweight REST API that accepts audio files, converts speech into text
using OpenAI Whisper, and returns the transcription with timestamps for
each segment.

The project focuses on practical engineering decisions, including API
design, input validation, concurrent request handling, error handling,
and resource management.

## 1. Features

- Upload WAV and MP3 audio files.
- Convert speech into text using Whisper.
- Return detected language and timestamped segments.
- Validate file format, empty uploads, and file size.
- Limit concurrent transcription requests.
- Remove temporary audio files after processing.
- Provide a health-check endpoint.
- Generate interactive API documentation through FastAPI.

## 2. Technology Stack

| Technology | Purpose |
|------------|---------|
| Python | Main programming language |
| FastAPI | REST API framework |
| OpenAI Whisper | Speech-to-text transcription |
| FFmpeg | Audio decoding and format support |
| asyncio | Asynchronous request handling and concurrency control |
| Uvicorn | ASGI application server |
| Temporary files | Store uploaded audio during processing |

### Why these technologies?

**Python:** Whisper has a mature Python interface, making it straightforward
to integrate speech recognition into an API.

**FastAPI:** Provides request validation, file uploads, HTTP error handling,
and automatically generated OpenAPI documentation.

**Whisper:** An open-source speech recognition model that supports automatic
language detection and provides timestamped transcription segments.

**FFmpeg:** Whisper relies on FFmpeg to decode audio files. This avoids
implementing separate audio decoders for different formats.

## 3. Architecture

The application follows a simple request-response architecture.

1. The client uploads an audio file through the REST API.
2. The API validates the file extension and size.
3. The uploaded audio is written to a temporary file.
4. A concurrency limit controls access to transcription.
5. Whisper processes the audio and generates text and timestamps.
6. The API returns the transcription as JSON.
7. The temporary file is deleted.

The current implementation processes audio synchronously from the client's
perspective: the client waits for the transcription response.

For longer audio files or higher traffic, this can be extended to an
asynchronous job-based workflow.

## 4. Design Decisions

### 4.1 Model Selection

The project uses Whisper's `base` model.

The model is loaded once when the application starts instead of being
loaded for every request.

This avoids repeated model initialization and reduces request overhead.

The `base` model is a practical starting point for a prototype. Model
accuracy, inference speed, and memory consumption should be evaluated
against representative audio before selecting a production model.

Larger models may improve recognition quality but generally require
more computational resources.

### 4.2 Audio Format Handling

The API accepts WAV and MP3 files.

File extensions are checked before processing to reject unsupported
uploads early.

Whisper uses FFmpeg to decode the audio, so the application does not
implement separate decoding logic for each supported format.

A file extension alone does not guarantee that the underlying content
is a valid audio file. A production implementation should also validate
the actual media content.

Additional formats, such as M4A, FLAC, and OGG, could be supported after
testing the corresponding decoding paths.

### 4.3 File Size Limit

The maximum upload size is 25 MB.

The application reads at most one byte beyond the configured limit
before rejecting the upload.

This keeps the basic implementation simple and prevents the entire
contents of an oversized upload from being read into memory.

For production deployments, request-body limits should also be enforced
at the reverse proxy or API gateway.

A file-size limit does not guarantee a reasonable processing time.
Audio duration limits may also be necessary.

### 4.4 Temporary File Storage

Uploaded audio is written to a temporary file because Whisper accepts
a file path for audio decoding.

The temporary file is removed in a `finally` block, including when
transcription fails.

This avoids retaining uploaded audio unnecessarily.

Temporary storage is appropriate for a prototype or a single-machine
deployment. Production systems may use private object storage when
audio needs to survive worker restarts or be processed asynchronously.

### 4.5 Timestamped Transcription

Whisper returns transcription segments with start and end times.

The API returns these timestamps in seconds, rounded to three decimal
places.

Each segment contains:

- `start`: Beginning of the segment.
- `end`: End of the segment.
- `text`: Recognized speech for the segment.

These are segment-level timestamps, not guaranteed word-level timestamps.

Word-level timing would require enabling Whisper's word timestamp
functionality and evaluating its accuracy for the intended use case.

### 4.6 Concurrency Handling

Transcription is CPU/GPU intensive and can take considerably longer
than ordinary API operations.

The implementation uses `asyncio.to_thread()` to run the synchronous
transcription function outside the asynchronous event loop.

An `asyncio.Semaphore` limits concurrent transcription calls to two
within the current application process.

This helps prevent excessive simultaneous model inference.

The limit is process-local. Running multiple Uvicorn workers creates
separate semaphores, so the total number of concurrent transcriptions
can exceed two.

For a larger deployment, a dedicated worker pool or task queue would
provide more explicit control over processing capacity.

### 4.7 Error Handling

The API returns appropriate HTTP errors for common input problems.

| Scenario | HTTP Status |
|----------|-------------|
| Unsupported file extension | 400 Bad Request |
| Empty audio file | 400 Bad Request |
| File exceeds size limit | 413 Content Too Large |
| Unexpected transcription failure | 500 Internal Server Error |

Internal exception details are not returned to clients.

Production deployments should additionally log exception details,
request IDs, and processing duration for troubleshooting.

### 4.8 Why Not Use a Background Queue Yet?

For this assessment, a direct request-response workflow keeps the
implementation small and easy to run locally.

A background queue becomes useful when:

- Audio files take a long time to process.
- Clients should not keep HTTP connections open.
- Jobs need automatic retries.
- Failed jobs must be recovered after worker restarts.
- Multiple workers need to process audio independently.

A possible future architecture would use Celery with Redis for job
management and PostgreSQL for persistent job status and transcripts.

## 5. API Endpoints

### POST /transcribe

Uploads an audio file and returns its transcription.

**Content type:** `multipart/form-data`

**Request field:** `file`

Supported extensions: `.wav`, `.mp3`

Maximum file size: 25 MB.

Example:

```bash
curl -X POST http://127.0.0.1:8000/transcribe \
  -F "file=@sample.wav"