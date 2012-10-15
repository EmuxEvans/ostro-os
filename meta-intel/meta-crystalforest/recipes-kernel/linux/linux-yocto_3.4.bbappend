FILESEXTRAPATHS_prepend := "${THISDIR}/${PN}:"

COMPATIBLE_MACHINE_crystalforest-stargo = "crystalforest-stargo"
KMACHINE_crystalforest-stargo  = "crystalforest"
KBRANCH_crystalforest-stargo  = "standard/common-pc-64/crystalforest"

SRCREV_machine_pn-linux-yocto_crystalforest-stargo ?= "0985844fa6235422c67ef269952fa4e765f252f9"
SRCREV_meta_pn-linux-yocto_crystalforest-stargo ?= "9e3bdb7344054264b750e53fbbb6394cc1c942ac"

COMPATIBLE_MACHINE_crystalforest-shumway = "crystalforest-shumway"
KMACHINE_crystalforest-shumway  = "crystalforest"
KBRANCH_crystalforest-shumway  = "standard/common-pc-64/crystalforest"

SRCREV_machine_pn-linux-yocto_crystalforest-shumway ?= "0985844fa6235422c67ef269952fa4e765f252f9"
SRCREV_meta_pn-linux-yocto_crystalforest-shumway ?= "9e3bdb7344054264b750e53fbbb6394cc1c942ac"

module_autoload_uio = "uio"
