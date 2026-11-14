# Dedicated recovery partitions: package the final image, without repacking boot.
RMX3371_INSTALLER_DIR := device/realme/RMX3371/installer
RMX3371_INSTALLER_TOOL := device/realme/RMX3371/tools/build_recovery_installer.py
RMX3371_INSTALLER_ZIP := $(PRODUCT_OUT)/twrp-installer-RMX3371.zip

$(RMX3371_INSTALLER_ZIP): $(PRODUCT_OUT)/recovery.img $(RMX3371_INSTALLER_TOOL) $(RMX3371_INSTALLER_DIR)/update-binary
	@echo "Packaging RMX3371 recovery installer: $@"
	$(hide) python3 $(RMX3371_INSTALLER_TOOL) --image $(PRODUCT_OUT)/recovery.img --output $@

.PHONY: recoveryzip
recoveryzip: $(RMX3371_INSTALLER_ZIP)
recoveryimage: $(RMX3371_INSTALLER_ZIP)
