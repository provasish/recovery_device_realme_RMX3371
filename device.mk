#
# Copyright (C) 2022 The Android Open Source Project
# Copyright (C) 2022 SebaUbuntu's TWRP device tree generator
# Copyright (C) 2026 AERA Recovery Project contributors
#
# SPDX-License-Identifier: Apache-2.0
#

LOCAL_PATH := device/realme/RMX3371

# realme GT Neo 3T launched on Android 12 with virtual A/B.
$(call inherit-product, $(SRC_TARGET_DIR)/product/virtual_ab_ota.mk)
BOARD_SHIPPING_API_LEVEL := 31
PRODUCT_SHIPPING_API_LEVEL := 31

PRODUCT_PLATFORM := kona
PRODUCT_USE_DYNAMIC_PARTITIONS := true

# Qualcomm HIDL boot control and recovery decryption helpers.
PRODUCT_PACKAGES += \
    android.hardware.boot@1.1-impl \
    android.hardware.boot@1.1-service \
    bootctrl.kona \
    libion \
    qcom_decrypt \
    qcom_decrypt_fbe

RECOVERY_LIBRARY_SOURCE_FILES += \
    $(TARGET_OUT_SHARED_LIBRARIES)/libion.so

# Dynamic partition and fastbootd tools.
PRODUCT_PACKAGES += \
    lpflash \
    lpmake \
    lpunpack

PRODUCT_SOONG_NAMESPACES += $(LOCAL_PATH)

$(call inherit-product, $(LOCAL_PATH)/aera_RMX3371.mk)
