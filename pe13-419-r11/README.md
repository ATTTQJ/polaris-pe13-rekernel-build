# PE13 Polaris 4.19 r11 candidate

Adds the observed legacy CRTC DSPP staging path on top of r10. The current-state setter validates and stages only the ten observed CRTC blob properties. The following frame applies them. Connector dither uses the existing atomic commit path. Use CI results as build evidence.
