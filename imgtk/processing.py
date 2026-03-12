from __future__ import annotations

import copy

from .deps import HAS_CV2, HAS_SCIPY, cv2, np, scipy_gaussian

PREVIEW_MAX_PX = 1440


def downscale_for_preview(img: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    if max(h, w) <= PREVIEW_MAX_PX:
        return img
    scale = PREVIEW_MAX_PX / max(h, w)
    nh, nw = max(1, int(h * scale)), max(1, int(w * scale))
    if HAS_CV2:
        return cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    row_idx = np.linspace(0, h - 1, nh, dtype=int)
    col_idx = np.linspace(0, w - 1, nw, dtype=int)
    return img[np.ix_(row_idx, col_idx)]


def gaussian(img: np.ndarray, sigma: float) -> np.ndarray:
    if HAS_SCIPY:
        return scipy_gaussian(img, sigma=sigma, mode="reflect")
    if HAS_CV2:
        k = max(3, int(sigma * 6) | 1)
        return cv2.GaussianBlur(img, (k, k), sigmaX=sigma, sigmaY=sigma)
    radius = max(1, int(sigma * 3))
    x = np.arange(-radius, radius + 1, dtype=np.float32)
    kern = np.exp(-x**2 / (2.0 * sigma**2))
    kern /= kern.sum()
    result = np.copy(img)
    for ax in (0, 1):
        result = np.apply_along_axis(lambda v: np.convolve(v, kern, mode="same"), ax, result)
    return result


class FilterParams:
    def __init__(self):
        self.denoise_enabled = False
        self.denoise_h = 10.0
        self.denoise_hcolor = 10.0
        self.denoise_template_window = 7
        self.denoise_search_window = 21

        self.sharpen_enabled = False
        self.sharpen_amount = 1.0
        self.sharpen_radius = 1.0

        self.highpass_enabled = False
        self.highpass_amount = 0.5
        self.highpass_radius = 5.0

        self.contrast_enabled = False
        self.contrast_value = 1.0
        self.brightness_value = 0.0

    def copy(self) -> "FilterParams":
        return copy.copy(self)


class ImageProcessor:
    @staticmethod
    def process(img: np.ndarray, params: FilterParams) -> np.ndarray:
        result = img.astype(np.float32)

        if params.denoise_enabled:
            result = ImageProcessor.denoise(
                result,
                params.denoise_h,
                params.denoise_hcolor,
                int(params.denoise_template_window),
                int(params.denoise_search_window),
            )
        if params.sharpen_enabled and params.sharpen_amount > 0:
            result = ImageProcessor.unsharp_mask(result, params.sharpen_amount, params.sharpen_radius)
        if params.highpass_enabled and params.highpass_amount > 0:
            result = ImageProcessor.highpass(result, params.highpass_amount, params.highpass_radius)
        if params.contrast_enabled:
            result = ImageProcessor.contrast(result, params.contrast_value, params.brightness_value)

        return result

    @staticmethod
    def denoise(img: np.ndarray, h: float, hcolor: float, tmpl_win: int, search_win: int) -> np.ndarray:
        if not HAS_CV2:
            return img

        tmpl_win = tmpl_win if tmpl_win % 2 == 1 else tmpl_win + 1
        search_win = search_win if search_win % 2 == 1 else search_win + 1

        rgb_f = np.clip(img[:, :, :3], 0, None).astype(np.float32)
        ch_max = rgb_f.max(axis=(0, 1), keepdims=True).clip(1e-6)
        rgb_u8 = ((rgb_f / ch_max) * 255).astype(np.uint8)

        bgr_u8 = cv2.cvtColor(rgb_u8, cv2.COLOR_RGB2BGR)
        bgr_den = cv2.fastNlMeansDenoisingColored(
            bgr_u8,
            None,
            h=float(h),
            hColor=float(hcolor),
            templateWindowSize=tmpl_win,
            searchWindowSize=search_win,
        )
        rgb_den = cv2.cvtColor(bgr_den, cv2.COLOR_BGR2RGB)
        rgb_out = (rgb_den.astype(np.float32) / 255.0) * ch_max

        result = img.copy()
        result[:, :, :3] = rgb_out
        return result

    @staticmethod
    def unsharp_mask(img: np.ndarray, amount: float, radius: float) -> np.ndarray:
        blurred = gaussian(img, sigma=radius)
        return img + amount * (img - blurred)

    @staticmethod
    def highpass(img: np.ndarray, amount: float, radius: float) -> np.ndarray:
        blurred = gaussian(img, sigma=radius)
        return img + amount * (img - blurred)

    @staticmethod
    def contrast(img: np.ndarray, contrast: float, brightness: float) -> np.ndarray:
        pivot = 0.18
        return pivot + contrast * (img - pivot) + brightness


def tonemap_display(img: np.ndarray, exposure: float = 0.0) -> np.ndarray:
    gain = 2.0**exposure
    rgb = img[:, :, :3].astype(np.float32) * gain
    rgb = rgb / (1.0 + rgb)
    np.clip(rgb, 0, 1, out=rgb)
    rgb = np.where(rgb <= 0.0031308, 12.92 * rgb, 1.055 * np.power(rgb, 1.0 / 2.4) - 0.055)
    np.clip(rgb, 0, 1, out=rgb)
    return (rgb * 255).astype(np.uint8)
