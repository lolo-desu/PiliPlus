# iOS Liquid Glass / unsigned IPA

This branch is based on upstream-style `main`, not the Linux presentation branches.
The existing navigation variant, destination ordering, unread badges, home tabs,
page structure, theme accent preference and player gestures are retained. iOS uses
native SwiftUI Liquid Glass behind the existing navigation controls, rounded
surfaces and Cupertino page transitions. iOS 26+ uses `glassEffect`; earlier iOS
uses an ultra-thin material fallback. Reduce Transparency and high contrast use
an opaque material. iOS 27 follows the same API availability path; device behavior
must still be verified on the OS version you install.

## Picture in Picture

On a playing video, reveal the existing player controls and tap the picture in
picture icon. You can then open another app. Close/restore the system window to
return playback to PiliPlus at the same time and rate. System play/pause and skip
controls affect the native PiP player; existing foreground controls are forwarded
while it owns playback. Native playback decodes the original video URL with the
same Referer and User-Agent and independently plays the separate audio URL when
present. No screen recording permission is needed.

Timestamped comments are preloaded from the existing danmaku service after its
account and rule filtering. The current and next six-minute segment are retained
natively, with refreshes at segment boundaries. Text, color, opacity, area,
font scale, minimum weight, and scrolling/top/bottom blocking preferences carry
into PiP. The native compositor draws comments directly into the decoded video
frames before submitting them to AVKit's sample-buffer PiP display layer.

Limits: PiP requires iOS 15+ and a codec/stream AVFoundation can decode (prefer
H.264 + AAC if a selected format fails). This first version adds PiP for on-demand
video, manually from the player; automatic background entry and live-room PiP
are not added. Advanced mode-7 comments, VIP gradient effects and AI occlusion
masks remain available in the original full player, but are not drawn in PiP.
Network/codec/startup failures return playback to the original player with a toast.
Compilation alone does not verify real-device background audio/video behavior.

## Build and sign

Run **Build for iOS** in GitHub Actions on branch `ios-liquid-glass`.
The `macos-26` job pins Flutter via `pubspec.yaml`, applies the original iOS
patches and builds with `--no-codesign`. The `iOS-glass-unsigned` artifact contains
`PiliPlus_ios_glass_unsigned_<version>.ipa` with the standard `Payload/Runner.app`
layout. No signing certificate or provisioning profile is used. Re-sign the app
and all its nested frameworks with your own signing tool before installation.
Keep Audio, AirPlay and Picture in Picture background capability enabled in your
signing configuration. The app already declares `UIBackgroundModes: audio`.

## Device checks

- Compare home tabs, bottom navigation variants, badges, video/reply layout and
  double-tap/drag/fullscreen gestures with the original app.
- Check dark/light themes, Reduce Transparency, high contrast and large text.
- Enter PiP on a video with scrolling, top and bottom comments; switch apps and
  lock/unlock the screen, checking smooth video, audible audio and comments.
- Pause/resume, skip forward/back, cross a six-minute comment boundary, and restore.
- Try a cached video, portrait video and an unsupported encoding. Failed startup
  must leave original playback usable; opening a new video must dispose old PiP.
