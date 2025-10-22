/**
 * OpenH264 Shim - Simple C API for Python ctypes
 * 
 * This provides a simplified C interface to OpenH264's C++ encoder API,
 * making it easier to use from Python via ctypes without dealing with
 * C++ vtables and complex initialization.
 */

#ifndef OPENH264_SHIM_H
#define OPENH264_SHIM_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

// Opaque handle type for the encoder
typedef void* h264_encoder_t;

// Error codes
typedef enum {
    H264_SUCCESS = 0,
    H264_ERROR_INVALID_PARAM = -1,
    H264_ERROR_MEMORY_ALLOC = -2,
    H264_ERROR_ENCODER_INIT = -3,
    H264_ERROR_ENCODE_FAILED = -4,
    H264_ERROR_NULL_ENCODER = -5,
    H264_ERROR_OUTPUT_BUFFER_TOO_SMALL = -6
} h264_result_t;

/**
 * Create and initialize an H.264 encoder
 * 
 * @param width Video width in pixels
 * @param height Video height in pixels  
 * @param fps Frame rate (frames per second)
 * @param bitrate Target bitrate in bits per second
 * @param keyint Keyframe interval (GOP size)
 * @param threads Number of threads to use (0 = auto)
 * @return Encoder handle on success, NULL on failure
 */
h264_encoder_t h264_encoder_create(int width, int height, int fps, 
                                   int bitrate, int keyint, int threads);

/**
 * Encode a single frame from I420 planar YUV data
 * 
 * @param encoder Encoder handle from h264_encoder_create
 * @param y Y plane data
 * @param u U plane data  
 * @param v V plane data
 * @param stride_y Y plane stride (typically width)
 * @param stride_u U plane stride (typically width/2)
 * @param stride_v V plane stride (typically width/2)
 * @param out_buf Output buffer for encoded data
 * @param out_buf_size Size of output buffer
 * @param out_size [OUT] Actual size of encoded data
 * @param is_keyframe [OUT] 1 if this frame is a keyframe, 0 otherwise
 * @return H264_SUCCESS on success, error code otherwise
 */
int h264_encoder_encode(h264_encoder_t encoder,
                        const uint8_t* y, const uint8_t* u, const uint8_t* v,
                        int stride_y, int stride_u, int stride_v,
                        uint8_t* out_buf, int out_buf_size,
                        int* out_size, int* is_keyframe);

/**
 * Force the next frame to be a keyframe (IDR)
 * 
 * @param encoder Encoder handle
 * @return H264_SUCCESS on success, error code otherwise
 */
int h264_encoder_force_idr(h264_encoder_t encoder);

/**
 * Destroy encoder and free resources
 * 
 * @param encoder Encoder handle to destroy
 */
void h264_encoder_destroy(h264_encoder_t encoder);

/**
 * Get version information
 * 
 * @return Version string
 */
const char* h264_encoder_version(void);

#ifdef __cplusplus
}
#endif

#endif // OPENH264_SHIM_H