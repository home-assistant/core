/**
 * OpenH264 Shim Implementation
 * 
 * Wraps OpenH264's C++ encoder API in a simple C interface
 * suitable for use with Python ctypes.
 */

#include "openh264_shim.h"
#include <wels/codec_api.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

// Internal encoder structure
typedef struct {
    ISVCEncoder* encoder;
    int width;
    int height;
    int fps;
    int bitrate;
    int keyint;
    int force_idr;
} encoder_context_t;

h264_encoder_t h264_encoder_create(int width, int height, int fps, 
                                   int bitrate, int keyint, int threads) {
    // Validate parameters
    if (width <= 0 || height <= 0 || fps <= 0 || bitrate <= 0 || keyint <= 0) {
        return NULL;
    }
    
    // Allocate context
    encoder_context_t* ctx = (encoder_context_t*)calloc(1, sizeof(encoder_context_t));
    if (!ctx) {
        return NULL;
    }
    
    // Store parameters
    ctx->width = width;
    ctx->height = height;
    ctx->fps = fps;
    ctx->bitrate = bitrate;
    ctx->keyint = keyint;
    ctx->force_idr = 0;
    
    // Create encoder
    int ret = WelsCreateSVCEncoder(&ctx->encoder);
    if (ret != 0 || !ctx->encoder) {
        free(ctx);
        return NULL;
    }
    
    // Initialize encoder parameters
    SEncParamExt param;
    memset(&param, 0, sizeof(SEncParamExt));
    
    ctx->encoder->GetDefaultParams(&param);
    
    // Set basic parameters
    param.iUsageType = CAMERA_VIDEO_REAL_TIME;
    param.fMaxFrameRate = (float)fps;
    param.iPicWidth = width;
    param.iPicHeight = height;
    param.iTargetBitrate = bitrate;
    param.iMaxBitrate = bitrate * 2;  // Allow burst up to 2x target
    param.iRCMode = RC_BITRATE_MODE;
    param.iTemporalLayerNum = 1;
    param.iSpatialLayerNum = 1;
    param.bEnableDenoise = false;
    param.bEnableBackgroundDetection = true;
    param.bEnableAdaptiveQuant = true;
    param.bEnableFrameSkip = true;
    param.bEnableLongTermReference = false;
    param.iLtrMarkPeriod = 30;
    param.uiIntraPeriod = keyint;
    param.eSpsPpsIdStrategy = CONSTANT_ID;
    param.bPrefixNalAddingCtrl = false;
    param.iLoopFilterDisableIdc = 0;
    param.iLoopFilterAlphaC0Offset = 0;
    param.iLoopFilterBetaOffset = 0;
    param.bEnableSSEI = true;
    param.bSimulcastAVC = false;
    param.iPaddingFlag = 0;
    param.iEntropyCodingModeFlag = 0;
    
    // Set spatial layer parameters
    param.sSpatialLayers[0].iVideoWidth = width;
    param.sSpatialLayers[0].iVideoHeight = height;
    param.sSpatialLayers[0].fFrameRate = (float)fps;
    param.sSpatialLayers[0].iSpatialBitrate = bitrate;
    param.sSpatialLayers[0].iMaxSpatialBitrate = bitrate * 2;
    param.sSpatialLayers[0].uiProfileIdc = PRO_BASELINE;
    param.sSpatialLayers[0].uiLevelIdc = LEVEL_3_1;
    param.sSpatialLayers[0].iDLayerQp = 26;
    param.sSpatialLayers[0].sSliceArgument.uiSliceMode = SM_SINGLE_SLICE;
    param.sSpatialLayers[0].sSliceArgument.uiSliceNum = 1;
    param.sSpatialLayers[0].sSliceArgument.uiSliceSizeConstraint = 0;
    
    // Set threading if specified
    if (threads > 0) {
        param.iMultipleThreadIdc = threads;
    } else {
        param.iMultipleThreadIdc = 1; // Single thread by default
    }
    
    // Initialize the encoder
    ret = ctx->encoder->InitializeExt(&param);
    if (ret != cmResultSuccess) {
        ctx->encoder->Uninitialize();
        WelsDestroySVCEncoder(ctx->encoder);
        free(ctx);
        return NULL;
    }
    
    // Set bitrate mode
    int video_format = videoFormatI420;
    ctx->encoder->SetOption(ENCODER_OPTION_DATAFORMAT, &video_format);
    
    return (h264_encoder_t)ctx;
}

int h264_encoder_encode(h264_encoder_t encoder,
                        const uint8_t* y, const uint8_t* u, const uint8_t* v,
                        int stride_y, int stride_u, int stride_v,
                        uint8_t* out_buf, int out_buf_size,
                        int* out_size, int* is_keyframe) {
    
    if (!encoder || !y || !u || !v || !out_buf || !out_size || !is_keyframe) {
        return H264_ERROR_INVALID_PARAM;
    }
    
    encoder_context_t* ctx = (encoder_context_t*)encoder;
    if (!ctx->encoder) {
        return H264_ERROR_NULL_ENCODER;
    }
    
    // Initialize outputs
    *out_size = 0;
    *is_keyframe = 0;
    
    // Prepare source picture
    SSourcePicture pic;
    memset(&pic, 0, sizeof(SSourcePicture));
    
    pic.iPicWidth = ctx->width;
    pic.iPicHeight = ctx->height;
    pic.iColorFormat = videoFormatI420;
    pic.iStride[0] = stride_y;
    pic.iStride[1] = stride_u;
    pic.iStride[2] = stride_v;
    pic.pData[0] = (unsigned char*)y;
    pic.pData[1] = (unsigned char*)u;
    pic.pData[2] = (unsigned char*)v;
    
    // Force IDR if requested
    if (ctx->force_idr) {
        ctx->encoder->ForceIntraFrame(true);
        ctx->force_idr = 0;
    }
    
    // Encode the frame
    SFrameBSInfo info;
    memset(&info, 0, sizeof(SFrameBSInfo));
    
    int ret = ctx->encoder->EncodeFrame(&pic, &info);
    if (ret != cmResultSuccess) {
        return H264_ERROR_ENCODE_FAILED;
    }
    
    // Check if we have output
    if (info.eFrameType == videoFrameTypeSkip) {
        // Frame was skipped, no output
        return H264_SUCCESS;
    }
    
    // Calculate total output size
    int total_size = 0;
    for (int layer = 0; layer < info.iLayerNum; ++layer) {
        for (int nal = 0; nal < info.sLayerInfo[layer].iNalCount; ++nal) {
            total_size += info.sLayerInfo[layer].pNalLengthInByte[nal];
        }
    }
    
    if (total_size > out_buf_size) {
        return H264_ERROR_OUTPUT_BUFFER_TOO_SMALL;
    }
    
    // Check if this is a keyframe based on frame type
    if (info.eFrameType == videoFrameTypeIDR || info.eFrameType == videoFrameTypeI) {
        *is_keyframe = 1;
    }
    
    // Copy NAL units to output buffer
    int offset = 0;
    for (int layer = 0; layer < info.iLayerNum; ++layer) {
        const SLayerBSInfo* layer_info = &info.sLayerInfo[layer];
        
        // Calculate layer size
        int layer_size = 0;
        for (int nal = 0; nal < layer_info->iNalCount; ++nal) {
            layer_size += layer_info->pNalLengthInByte[nal];
        }
        
        if (offset + layer_size > out_buf_size) {
            return H264_ERROR_OUTPUT_BUFFER_TOO_SMALL;
        }
        
        memcpy(out_buf + offset, layer_info->pBsBuf, layer_size);
        offset += layer_size;
    }
    
    *out_size = offset;
    return H264_SUCCESS;
}

int h264_encoder_force_idr(h264_encoder_t encoder) {
    if (!encoder) {
        return H264_ERROR_INVALID_PARAM;
    }
    
    encoder_context_t* ctx = (encoder_context_t*)encoder;
    if (!ctx->encoder) {
        return H264_ERROR_NULL_ENCODER;
    }
    
    ctx->force_idr = 1;
    return H264_SUCCESS;
}

void h264_encoder_destroy(h264_encoder_t encoder) {
    if (!encoder) {
        return;
    }
    
    encoder_context_t* ctx = (encoder_context_t*)encoder;
    
    if (ctx->encoder) {
        ctx->encoder->Uninitialize();
        WelsDestroySVCEncoder(ctx->encoder);
    }
    
    free(ctx);
}

const char* h264_encoder_version(void) {
    return "OpenH264 Shim v1.0.0";
}