"""File system operation API endpoints."""

import os
import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, File, UploadFile
from pydantic import BaseModel

from backend.utils.helpers import sanitize_path
from backend.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

# Extension → folder name mapping for Downloads organiser
_EXT_MAP: dict[str, str] = {
    # Images
    **dict.fromkeys([".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".ico", ".tiff"], "images"),
    # Documents
    **dict.fromkeys([".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".md", ".csv", ".odt"], "documents"),
    # Videos
    **dict.fromkeys([".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm"], "videos"),
    # Audio
    **dict.fromkeys([".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a"], "audio"),
    # Archives
    **dict.fromkeys([".zip", ".tar", ".gz", ".bz2", ".rar", ".7z", ".xz"], "archives"),
    # Code
    **dict.fromkeys([".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".java", ".c", ".cpp", ".go", ".rs", ".rb", ".sh"], "code"),
}


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class SearchRequest(BaseModel):
    """Request body for the file search endpoint."""

    query: str
    path: str = "~"


class FolderCreateRequest(BaseModel):
    """Request body for the folder creation endpoint."""

    path: str


class RenameRequest(BaseModel):
    """Request body for the rename endpoint."""

    old_path: str
    new_path: str


class MoveRequest(BaseModel):
    """Request body for the move endpoint."""

    source: str
    destination: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/search", summary="Search for files matching a query")
async def search_files(request: SearchRequest) -> dict[str, Any]:
    """Walk *path* recursively and return files whose names contain *query*.

    Args:
        request: Search parameters — the query string and root path to search.

    Returns:
        Dict with ``matches`` (list of absolute path strings) and ``total``.
    """
    try:
        root = sanitize_path(request.path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not root.exists():
        raise HTTPException(status_code=404, detail=f"Path '{root}' does not exist.")

    query_lower = request.query.lower()
    matches: list[str] = []

    for dirpath, _dirs, files in os.walk(root):
        for filename in files:
            if query_lower in filename.lower():
                matches.append(os.path.join(dirpath, filename))
        if len(matches) >= 500:  # cap results
            break

    logger.info("File search for '%s' in '%s': %d matches", request.query, root, len(matches))
    return {"matches": matches, "total": len(matches)}


@router.post("/create-folder", summary="Create a new directory")
async def create_folder(request: FolderCreateRequest) -> dict[str, str]:
    """Create a directory (and any missing parents) at the given path.

    Args:
        request: The path where the folder should be created.

    Returns:
        Dict with ``message`` and ``path``.
    """
    try:
        target = sanitize_path(request.path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Could not create folder: {exc}") from exc

    logger.info("Created folder: %s", target)
    return {"message": "Folder created successfully.", "path": str(target)}


@router.post("/rename", summary="Rename a file or directory")
async def rename_path(request: RenameRequest) -> dict[str, str]:
    """Rename (or move) a filesystem entry from *old_path* to *new_path*.

    Args:
        request: Old and new path strings.

    Returns:
        Dict with ``message``, ``old_path``, ``new_path``.
    """
    try:
        old = sanitize_path(request.old_path)
        new = sanitize_path(request.new_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not old.exists():
        raise HTTPException(status_code=404, detail=f"'{old}' does not exist.")

    try:
        old.rename(new)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Rename failed: {exc}") from exc

    logger.info("Renamed '%s' → '%s'", old, new)
    return {"message": "Renamed successfully.", "old_path": str(old), "new_path": str(new)}


@router.post("/move", summary="Move a file or directory")
async def move_path(request: MoveRequest) -> dict[str, str]:
    """Move *source* to *destination* using :func:`shutil.move`.

    Args:
        request: Source and destination path strings.

    Returns:
        Dict with ``message``, ``source``, ``destination``.
    """
    try:
        src = sanitize_path(request.source)
        dst = sanitize_path(request.destination)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not src.exists():
        raise HTTPException(status_code=404, detail=f"'{src}' does not exist.")

    try:
        shutil.move(str(src), str(dst))
    except (shutil.Error, OSError) as exc:
        raise HTTPException(status_code=500, detail=f"Move failed: {exc}") from exc

    logger.info("Moved '%s' → '%s'", src, dst)
    return {"message": "Moved successfully.", "source": str(src), "destination": str(dst)}


@router.get("/organize-downloads", summary="Organise ~/Downloads by file type")
async def organize_downloads() -> dict[str, Any]:
    """Move files in ~/Downloads into categorised subdirectories.

    Categories: images, documents, videos, audio, archives, code, other.
    Subdirectories are created automatically.

    Returns:
        Dict with ``moved`` count and ``details`` list of move records.
    """
    downloads = Path.home() / "Downloads"
    if not downloads.exists():
        raise HTTPException(status_code=404, detail="~/Downloads directory not found.")

    moved: list[dict[str, str]] = []
    errors: list[str] = []

    for entry in downloads.iterdir():
        if entry.is_dir():
            continue  # Skip subdirectories

        ext = entry.suffix.lower()
        category = _EXT_MAP.get(ext, "other")
        target_dir = downloads / category
        target_dir.mkdir(exist_ok=True)

        target_path = target_dir / entry.name
        # Avoid overwriting existing files by suffixing
        if target_path.exists():
            stem = entry.stem
            suffix = entry.suffix
            counter = 1
            while target_path.exists():
                target_path = target_dir / f"{stem}_{counter}{suffix}"
                counter += 1

        try:
            shutil.move(str(entry), str(target_path))
            moved.append({"file": entry.name, "category": category, "destination": str(target_path)})
        except (shutil.Error, OSError) as exc:
            errors.append(f"{entry.name}: {exc}")
            logger.error("Failed to move '%s': %s", entry.name, exc)

    logger.info("Organised Downloads: %d files moved, %d errors.", len(moved), len(errors))
    return {
        "moved": len(moved),
        "details": moved,
        "errors": errors,
    }


@router.post("/upload", summary="Upload a file or image for analysis")
async def upload_file(file: UploadFile = File(...)) -> dict[str, Any]:
    """Upload a file or image to the local server storage.

    Args:
        file: Multipart uploaded file.

    Returns:
        Dict containing filename, local filepath, size, content type, and flags.
    """
    upload_dir = Path(__file__).parent.parent / "uploads"
    upload_dir.mkdir(exist_ok=True)

    # Clean the filename and construct path
    safe_filename = Path(file.filename or "uploaded_file").name
    file_path = upload_dir / safe_filename
    
    # Avoid collision by appending integer
    if file_path.exists():
        stem = file_path.stem
        suffix = file_path.suffix
        counter = 1
        while file_path.exists():
            file_path = upload_dir / f"{stem}_{counter}{suffix}"
            counter += 1

    try:
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
            
        logger.info("File upload success: %s saved to %s", safe_filename, file_path)
        
        # Check if content type or extension is an image
        ext = file_path.suffix.lower()
        is_image = (
            file.content_type.startswith("image/") 
            or ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff")
        )
        
        return {
            "filename": safe_filename,
            "filepath": str(file_path),
            "content_type": file.content_type,
            "size": len(content),
            "is_image": is_image,
        }
    except Exception as exc:
        logger.error("Failed to write uploaded file '%s': %s", safe_filename, exc)
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {exc}")
