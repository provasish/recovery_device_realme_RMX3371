#
# Copyright (C) 2022 The Android Open Source Project
# Copyright (C) 2026 AERA Recovery Project contributors
#
# SPDX-License-Identifier: Apache-2.0
#

$(call inherit-product, $(SRC_TARGET_DIR)/product/base.mk)
$(call inherit-product, $(SRC_TARGET_DIR)/product/core_64_bit_only.mk)
$(call inherit-product, $(SRC_TARGET_DIR)/product/emulated_storage.mk)
$(call inherit-product, vendor/twrp/config/common.mk)
$(call inherit-product, device/realme/RMX3371/device.mk)

PRODUCT_DEVICE := RMX3371
PRODUCT_NAME := twrp_RMX3371
PRODUCT_BRAND := realme
PRODUCT_MODEL := GT Neo 3T
PRODUCT_MANUFACTURER := realme
PRODUCT_RELEASE_NAME := RMX3371

AERA_STATUS_ICONS_ALIGN := center
