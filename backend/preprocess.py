"""Smart preprocessing for phone-captured photos of old prints.

Features:
  1. Multi-photo glare removal — merge 2 shots taken at different angles
  2. Auto-crop — detect photo edges within a phone shot
  3. Perspective correction — straighten tilted/skewed photos
  4. Scratch & crease detection — mask and inpaint minor damage
  5. Adaptive contrast & denoising — prepare for AI pipeline
"""

import io
import numpy as np
from PIL import Image, ImageFilter, ImageStat

# OpenCV is optional — functions degrade gracefully without it
try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


# ── 1. Multi-photo glare removal ────────────────────────────────────

def merge_two_angles(img_bytes_1: bytes, img_bytes_2: bytes) -> bytes:
    """Merge two photos of the same print taken at different angles.

    Strategy:
      - Align image 2 to image 1 using feature-based homography
      - Detect glare (bright overexposed regions) in both
      - Composite: prefer non-glare pixels from either image
      - Fallback: if alignment fails, use the image with less glare
    """
    img1 = _bytes_to_cv2(img_bytes_1)
    img2 = _bytes_to_cv2(img_bytes_2)

    if not HAS_CV2:
        # Fallback: return image with lower average brightness (less glare)
        b1 = np.mean(img1)
        b2 = np.mean(img2)
        return img_bytes_1 if b1 <= b2 else img_bytes_2

    # Align img2 to img1 coordinate space
    aligned_img2 = _align_images(img1, img2)
    if aligned_img2 is None:
        # Alignment failed — pick the one with less glare
        g1 = _glare_percentage(img1)
        g2 = _glare_percentage(img2)
        return img_bytes_1 if g1 <= g2 else img_bytes_2

    # Create glare masks for both images
    glare_mask1 = _detect_glare_mask(img1)
    glare_mask2 = _detect_glare_mask(aligned_img2)

    # Composite: where img1 has glare, take from img2 and vice versa
    result = img1.copy()

    # Regions where img1 has glare but img2 doesn't → use img2
    use_img2 = glare_mask1 & ~glare_mask2
    result[use_img2] = aligned_img2[use_img2]

    # Regions where both have glare → blend (average)
    both_glare = glare_mask1 & glare_mask2
    if np.any(both_glare):
        result[both_glare] = (
            img1[both_glare].astype(np.float32) * 0.5 +
            aligned_img2[both_glare].astype(np.float32) * 0.5
        ).astype(np.uint8)

    # Smooth seams along mask edges
    result = _smooth_seams(result, img1, aligned_img2, use_img2)

    return _cv2_to_bytes(result)


def _align_images(img_ref: np.ndarray, img_to_align: np.ndarray) -> np.ndarray | None:
    """Align img_to_align to img_ref using ORB features + homography."""
    gray1 = cv2.cvtColor(img_ref, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(img_to_align, cv2.COLOR_BGR2GRAY)

    orb = cv2.ORB_create(5000)
    kp1, desc1 = orb.detectAndCompute(gray1, None)
    kp2, desc2 = orb.detectAndCompute(gray2, None)

    if desc1 is None or desc2 is None or len(kp1) < 10 or len(kp2) < 10:
        return None

    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    matches = bf.knnMatch(desc2, desc1, k=2)

    # Lowe's ratio test
    good = []
    for pair in matches:
        if len(pair) == 2:
            m, n = pair
            if m.distance < 0.75 * n.distance:
                good.append(m)

    if len(good) < 10:
        return None

    src_pts = np.float32([kp2[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp1[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)

    H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
    if H is None:
        return None

    h, w = img_ref.shape[:2]
    aligned = cv2.warpPerspective(img_to_align, H, (w, h))
    return aligned


def _detect_glare_mask(img: np.ndarray, threshold: int = 220) -> np.ndarray:
    """Detect overexposed (glare) regions. Returns boolean mask (H, W)."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    bright = gray > threshold
    # Expand glare regions slightly to cover borders
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    bright = cv2.dilate(bright.astype(np.uint8), kernel, iterations=2).astype(bool)
    # Broadcast to 3-channel mask shape (H, W, 3)
    return np.stack([bright] * 3, axis=-1)


def _glare_percentage(img: np.ndarray) -> float:
    """What percentage of pixels are overexposed."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return np.mean(gray > 220) * 100


def _smooth_seams(result, img1, img2, mask):
    """Feather the edges where we switch between images to avoid visible seams."""
    # Create single-channel mask
    mask_1ch = mask[:, :, 0].astype(np.uint8) * 255
    # Blur the mask to create smooth transitions
    blurred = cv2.GaussianBlur(mask_1ch, (31, 31), 0)
    alpha = blurred.astype(np.float32) / 255.0
    alpha = np.stack([alpha] * 3, axis=-1)

    result_float = (
        img1.astype(np.float32) * (1 - alpha) +
        img2.astype(np.float32) * alpha
    )
    return result_float.astype(np.uint8)


# ── 2. Auto-crop: detect photo within phone shot ────────────────────

def auto_crop(img_bytes: bytes) -> bytes:
    """Detect and crop the old photo from a phone snapshot.

    Finds the largest rectangular contour (the photo) and crops to it.
    """
    if not HAS_CV2:
        return img_bytes

    img = _bytes_to_cv2(img_bytes)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Edge detection
    edges = cv2.Canny(blurred, 30, 100)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    edges = cv2.dilate(edges, kernel, iterations=2)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return img_bytes

    # Find largest contour by area
    largest = max(contours, key=cv2.contourArea)
    img_area = img.shape[0] * img.shape[1]

    # Only crop if contour is between 10% and 95% of image (otherwise it IS the photo)
    contour_area = cv2.contourArea(largest)
    if contour_area < img_area * 0.10 or contour_area > img_area * 0.95:
        return img_bytes

    # Approximate contour to polygon
    peri = cv2.arcLength(largest, True)
    approx = cv2.approxPolyDP(largest, 0.02 * peri, True)

    if len(approx) == 4:
        # Found a quadrilateral — do perspective correction
        return _perspective_transform(img, approx.reshape(4, 2))
    else:
        # Not a clean quad — just use bounding rectangle
        x, y, w, h = cv2.boundingRect(largest)
        cropped = img[y:y+h, x:x+w]
        return _cv2_to_bytes(cropped)


# ── 3. Perspective correction ────────────────────────────────────────

def correct_perspective(img_bytes: bytes) -> bytes:
    """Straighten a tilted/skewed photo using edge detection."""
    if not HAS_CV2:
        return img_bytes
    return auto_crop(img_bytes)  # Auto-crop already includes perspective fix


def _perspective_transform(img: np.ndarray, pts: np.ndarray) -> bytes:
    """Apply perspective transform given 4 corner points."""
    # Order points: top-left, top-right, bottom-right, bottom-left
    rect = _order_points(pts.astype(np.float32))
    tl, tr, br, bl = rect

    # Compute new dimensions
    width_top = np.linalg.norm(tr - tl)
    width_bot = np.linalg.norm(br - bl)
    max_width = int(max(width_top, width_bot))

    height_left = np.linalg.norm(bl - tl)
    height_right = np.linalg.norm(br - tr)
    max_height = int(max(height_left, height_right))

    dst = np.array([
        [0, 0],
        [max_width - 1, 0],
        [max_width - 1, max_height - 1],
        [0, max_height - 1],
    ], dtype=np.float32)

    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(img, M, (max_width, max_height))
    return _cv2_to_bytes(warped)


def _order_points(pts):
    """Order 4 points as: top-left, top-right, bottom-right, bottom-left."""
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1)
    return np.array([
        pts[np.argmin(s)],
        pts[np.argmin(d)],
        pts[np.argmax(s)],
        pts[np.argmax(d)],
    ], dtype=np.float32)


# ── 4. Scratch & crease detection + inpainting ──────────────────────

def remove_scratches(img_bytes: bytes) -> bytes:
    """Detect thin bright/dark lines (scratches) and inpaint them."""
    if not HAS_CV2:
        return img_bytes

    img = _bytes_to_cv2(img_bytes)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Detect scratches as thin bright lines
    # Use morphological blackhat (bright scratches on dark bg)
    kernel_line = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 15))
    blackhat_v = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, kernel_line)

    kernel_line_h = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 1))
    blackhat_h = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, kernel_line_h)

    scratch_mask = cv2.add(blackhat_v, blackhat_h)
    _, scratch_binary = cv2.threshold(scratch_mask, 40, 255, cv2.THRESH_BINARY)

    # Only inpaint if scratches are detected (not too many — that would be noise)
    scratch_ratio = np.mean(scratch_binary > 0)
    if scratch_ratio < 0.001 or scratch_ratio > 0.15:
        return img_bytes

    # Dilate mask slightly so inpainting covers edges
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    scratch_binary = cv2.dilate(scratch_binary, kernel, iterations=1)

    inpainted = cv2.inpaint(img, scratch_binary, 3, cv2.INPAINT_TELEA)
    return _cv2_to_bytes(inpainted)


# ── 5. Adaptive contrast & denoising ────────────────────────────────

def enhance_for_restoration(img_bytes: bytes) -> bytes:
    """Light preprocessing: adaptive contrast + gentle denoising."""
    if not HAS_CV2:
        return _pil_enhance(img_bytes)

    img = _bytes_to_cv2(img_bytes)

    # Gentle denoising (preserve details, just reduce camera noise)
    denoised = cv2.fastNlMeansDenoisingColored(img, None, 5, 5, 7, 21)

    # CLAHE for adaptive contrast (helps with faded photos)
    lab = cv2.cvtColor(denoised, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    enhanced = cv2.merge([l, a, b])
    enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)

    return _cv2_to_bytes(enhanced)


def _pil_enhance(img_bytes: bytes) -> bytes:
    """Fallback PIL-based enhancement when OpenCV is unavailable."""
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    # Simple sharpen + auto-contrast
    from PIL import ImageOps
    img = ImageOps.autocontrast(img, cutoff=1)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


# ── Helpers ──────────────────────────────────────────────────────────

def _bytes_to_cv2(img_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(img_bytes, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def _cv2_to_bytes(img: np.ndarray) -> bytes:
    _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return buf.tobytes()
