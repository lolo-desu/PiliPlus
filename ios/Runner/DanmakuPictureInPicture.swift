import AVFoundation
import AVKit
import CoreImage
import Flutter
import UIKit

/// Compose decoded video and timestamped comments into the same pixel buffer.
/// AVKit therefore displays comments even outside the Flutter view hierarchy.
@available(iOS 15.0, *)
final class DanmakuPictureInPicture: NSObject, AVPictureInPictureControllerDelegate,
  AVPictureInPictureSampleBufferPlaybackDelegate {
  private let channel: FlutterMethodChannel
  private let layer = AVSampleBufferDisplayLayer()
  private let sourceView = UIView()
  // UIKit rendering apps cannot rely on GPU access while backgrounded.
  private let ciContext = CIContext(options: [.useSoftwareRenderer: true, .cacheIntermediates: false])
  private var pip: AVPictureInPictureController?
  private var video: AVPlayer?
  private var audio: AVPlayer?
  private var output: AVPlayerItemVideoOutput?
  private var timer: Timer?
  private var possibleObservation: NSKeyValueObservation?
  private var statusObservation: NSKeyValueObservation?
  private var audioObservation: NSKeyValueObservation?
  private var pendingResult: FlutterResult?
  private var sessionID = UUID()
  private var initialPosition = 0.0
  private var speed: Float = 1
  private var playing = true
  private var duration = 0.0
  private var live = false
  private var lastReported = -1.0
  private var lastReportedPlaying: Bool?
  private var prepared = false
  private var comments: [[String: Any]] = []
  private var active: [(text: String, color: UIColor, mode: Int, start: Double, lane: Int)] = []
  private var commentIndex = 0
  private var laneEnds = Array(repeating: -10.0, count: 6)
  private var lastPosition = -1.0
  private var opacity: CGFloat = 1
  private var fontSize: CGFloat = 20
  private var area: CGFloat = 0.7
  private var pool: CVPixelBufferPool?
  private var lastImage: CIImage?
  private var timebase: CMTimebase?

  init(messenger: FlutterBinaryMessenger) {
    channel = FlutterMethodChannel(name: "piliplus/ios_pip", binaryMessenger: messenger)
    super.init()
    channel.setMethodCallHandler { [weak self] call, result in
      guard let self else { result(FlutterError(code: "disposed", message: "PiP unavailable", details: nil)); return }
      switch call.method {
      case "start": self.start(call.arguments as? [String: Any] ?? [:], result: result)
      case "danmaku":
        self.replaceComments(call.arguments as? [[String: Any]] ?? [])
        result(nil)
      case "playing": self.setPlaying(call.arguments as? Bool ?? false); result(nil)
      case "speed":
        self.speed = (call.arguments as? NSNumber)?.floatValue ?? 1
        self.setPlaying(self.playing); result(nil)
      case "seek":
        let seconds = (call.arguments as? NSNumber)?.doubleValue ?? 0
        self.seek(seconds) { self.setPlaying(self.playing); result(nil) }
      case "dispose": self.cleanup(report: false); result(nil)
      default: result(FlutterMethodNotImplemented)
      }
    }
  }

  private func start(_ args: [String: Any], result: @escaping FlutterResult) {
    guard AVPictureInPictureController.isPictureInPictureSupported() else {
      result(FlutterError(code: "unsupported", message: "此设备不支持画中画", details: nil)); return
    }
    guard video == nil, let path = args["video"] as? String, let url = mediaURL(path) else {
      result(FlutterError(code: "busy", message: "画中画正在使用或视频地址无效", details: nil)); return
    }
    guard let window = UIApplication.shared.connectedScenes.compactMap({ $0 as? UIWindowScene })
      .flatMap({ $0.windows }).first(where: { $0.isKeyWindow }) else {
      result(FlutterError(code: "window", message: "未找到播放窗口", details: nil)); return
    }
    sessionID = UUID()
    let currentSessionID = sessionID
    pendingResult = result
    initialPosition = (args["position"] as? NSNumber)?.doubleValue ?? 0
    duration = (args["duration"] as? NSNumber)?.doubleValue ?? 0
    speed = (args["speed"] as? NSNumber)?.floatValue ?? 1
    playing = args["playing"] as? Bool ?? true
    live = args["live"] as? Bool ?? false
    opacity = CGFloat((args["opacity"] as? NSNumber)?.doubleValue ?? 1)
    fontSize = min(30, max(14, CGFloat((args["fontScale"] as? NSNumber)?.doubleValue ?? 1) * 20))
    area = min(1, max(0.2, CGFloat((args["area"] as? NSNumber)?.doubleValue ?? 0.7)))
    replaceComments(args["comments"] as? [[String: Any]] ?? [])
    let headers = args["headers"] as? [String: String] ?? [:]
    let item = AVPlayerItem(asset: AVURLAsset(url: url, options: ["AVURLAssetHTTPHeaderFieldsKey": headers]))
    let output = AVPlayerItemVideoOutput(pixelBufferAttributes: [
      kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA])
    item.add(output)
    self.output = output
    video = AVPlayer(playerItem: item)
    let volume = min(1, max(0, (args["volume"] as? NSNumber)?.floatValue ?? 1))
    video?.volume = volume
    if let audioPath = args["audio"] as? String, !audioPath.isEmpty, let audioURL = mediaURL(audioPath) {
      video?.isMuted = true
      audio = AVPlayer(playerItem: AVPlayerItem(asset: AVURLAsset(url: audioURL,
        options: ["AVURLAssetHTTPHeaderFieldsKey": headers])))
    }
    audio?.volume = volume
    do {
      try AVAudioSession.sharedInstance().setCategory(.playback, mode: .moviePlayback)
      try AVAudioSession.sharedInstance().setActive(true)
    } catch { fail("音频会话启动失败：\(error.localizedDescription)"); return }
    let ratio = max(0.3, min(3, (args["aspect"] as? NSNumber)?.doubleValue ?? 16.0 / 9.0))
    let width = CGFloat(Int(640 * min(1, ratio)) / 2 * 2)
    let height = CGFloat(Int(width / ratio) / 2 * 2)
    CVPixelBufferPoolCreate(nil, nil, [
      kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA,
      kCVPixelBufferWidthKey as String: Int(width),
      kCVPixelBufferHeightKey as String: Int(height),
      kCVPixelBufferCGImageCompatibilityKey as String: true,
      kCVPixelBufferCGBitmapContextCompatibilityKey as String: true,
      kCVPixelBufferIOSurfacePropertiesKey as String: [:]
    ] as CFDictionary, &pool)
    // A visible source layer is required by AVKit. It is removed on dismissal.
    sourceView.frame = CGRect(x: window.safeAreaInsets.left + 8,
      y: window.safeAreaInsets.top + 8, width: 160, height: 160 / ratio)
    if let rect = args["rect"] as? [Double], rect.count == 4, rect[2] > 0, rect[3] > 0 {
      sourceView.frame = CGRect(x: rect[0], y: rect[1], width: rect[2], height: rect[3])
    }
    CMTimebaseCreateWithSourceClock(allocator: kCFAllocatorDefault,
      sourceClock: CMClockGetHostTimeClock(), timebaseOut: &timebase)
    layer.controlTimebase = timebase
    if let timebase { CMTimebaseSetTime(timebase, time: CMTime(seconds: initialPosition, preferredTimescale: 600)) }
    sourceView.alpha = 1
    sourceView.backgroundColor = .black
    sourceView.isUserInteractionEnabled = false
    layer.frame = sourceView.bounds
    layer.videoGravity = .resizeAspect
    sourceView.layer.addSublayer(layer)
    window.addSubview(sourceView)
    pip = AVPictureInPictureController(contentSource: .init(
      sampleBufferDisplayLayer: layer, playbackDelegate: self))
    pip?.delegate = self
    pip?.requiresLinearPlayback = live
    possibleObservation = pip?.observe(\.isPictureInPicturePossible, options: [.new]) { [weak self] controller, _ in
      guard controller.isPictureInPicturePossible else { return }
      DispatchQueue.main.async { self?.pip?.startPictureInPicture() }
    }
    statusObservation = item.observe(\.status, options: [.initial, .new]) { [weak self] _, _ in
      DispatchQueue.main.async { self?.prepareWhenReady() }
    }
    if let audioItem = audio?.currentItem {
      audioObservation = audioItem.observe(\.status, options: [.initial, .new]) { [weak self] _, _ in
        DispatchQueue.main.async { self?.prepareWhenReady() }
      }
    }
    // Decode/network failures must return playback ownership to Flutter.
    DispatchQueue.main.asyncAfter(deadline: .now() + 20) { [weak self] in
      if self?.sessionID == currentSessionID && self?.pendingResult != nil { self?.fail("当前播放源启动超时") }
    }
  }

  private func mediaURL(_ path: String) -> URL? {
    path.hasPrefix("/") ? URL(fileURLWithPath: path) : URL(string: path)
  }
  private func prepareWhenReady() {
    if video?.currentItem?.status == .failed || audio?.currentItem?.status == .failed {
      fail("当前播放源解码失败"); return
    }
    guard !prepared, video?.currentItem?.status == .readyToPlay,
      audio == nil || audio?.currentItem?.status == .readyToPlay else { return }
    prepared = true
    seek(initialPosition) { [weak self] in
      guard let self, self.video != nil else { return }
      self.setPlaying(self.playing)
      let timer = Timer(timeInterval: 1.0 / 30.0, repeats: true) { [weak self] _ in self?.render() }
      self.timer = timer
      RunLoop.main.add(timer, forMode: .common)
    }
  }

  private func replaceComments(_ items: [[String: Any]]) {
    let now = video?.currentTime().seconds ?? initialPosition
    comments = items.sorted { ($0["time"] as? Double ?? 0) < ($1["time"] as? Double ?? 0) }
    commentIndex = comments.firstIndex { ($0["time"] as? Double ?? 0) >= now } ?? comments.count
  }
  private func setPlaying(_ value: Bool) {
    playing = value
    if value { video?.rate = speed; audio?.rate = speed }
    else { video?.pause(); audio?.pause() }
    if let timebase { CMTimebaseSetRate(timebase, rate: value ? Double(speed) : 0) }
    pip?.invalidatePlaybackState()
  }
  private func seek(_ seconds: Double, completion: @escaping () -> Void) {
    let time = CMTime(seconds: max(0, seconds), preferredTimescale: 600)
    let group = DispatchGroup()
    for player in [video, audio].compactMap({ $0 }) {
      group.enter()
      player.seek(to: time, toleranceBefore: .zero, toleranceAfter: .zero) { _ in group.leave() }
    }
    group.notify(queue: .main) { [weak self] in
      self?.active.removeAll()
      self?.laneEnds = Array(repeating: -10, count: 6)
      self?.lastPosition = -1
      if let timebase = self?.timebase { CMTimebaseSetTime(timebase, time: time) }
      completion()
    }
  }

  private func render() {
    guard let video, let output, let pool else { return }
    let position = video.currentTime().seconds
    guard position.isFinite else { return }
    if position < lastPosition {
      active.removeAll(); laneEnds = Array(repeating: -10, count: 6)
      commentIndex = comments.firstIndex { ($0["time"] as? Double ?? 0) >= position } ?? comments.count
    }
    lastPosition = position
    // Wall-clock polling keeps audio held and controls updated during video stalls.
    if CACurrentMediaTime() - lastReported >= 0.25 || lastReportedPlaying != playing {
      lastReported = CACurrentMediaTime()
      lastReportedPlaying = playing
      if let timebase { CMTimebaseSetTime(timebase, time: CMTime(seconds: position, preferredTimescale: 600)) }
      if playing { audio?.rate = video.timeControlStatus == .playing ? speed : 0 }
      channel.invokeMethod("position", arguments: ["position": position, "playing": playing])
      if let audio, playing, abs(audio.currentTime().seconds - position) > 0.35 {
        audio.seek(to: video.currentTime(), toleranceBefore: .zero, toleranceAfter: .zero)
      }
    }
    if playing && !live && duration > 0 && position >= duration - 0.1 { setPlaying(false) }
    let itemTime = output.itemTime(forHostTime: CACurrentMediaTime())
    if output.hasNewPixelBuffer(forItemTime: itemTime), let buffer = output.copyPixelBuffer(forItemTime: itemTime, itemTimeForDisplay: nil) {
      lastImage = CIImage(cvPixelBuffer: buffer)
    }
    guard let image = lastImage else { return }
    if layer.status == .failed { layer.flush() }
    guard layer.isReadyForMoreMediaData else { return }
    var destination: CVPixelBuffer?
    guard CVPixelBufferPoolCreatePixelBuffer(nil, pool, &destination) == kCVReturnSuccess,
      let destination else { return }
    let width = CGFloat(CVPixelBufferGetWidth(destination)), height = CGFloat(CVPixelBufferGetHeight(destination))
    let scale = min(width / image.extent.width, height / image.extent.height)
    let fitted = image.transformed(by: CGAffineTransform(scaleX: scale, y: scale))
      .transformed(by: CGAffineTransform(translationX: (width - image.extent.width * scale) / 2,
        y: (height - image.extent.height * scale) / 2))
    let background = CIImage(color: .black).cropped(to: CGRect(x: 0, y: 0, width: width, height: height))
    ciContext.render(fitted.composited(over: background), to: destination)
    drawComments(destination, position: position, width: width, height: height)
    var description: CMVideoFormatDescription?
    CMVideoFormatDescriptionCreateForImageBuffer(allocator: kCFAllocatorDefault,
      imageBuffer: destination, formatDescriptionOut: &description)
    guard let description else { return }
    var timing = CMSampleTimingInfo(duration: CMTime(value: 1, timescale: 30),
      presentationTimeStamp: CMTime(seconds: position, preferredTimescale: 600),
      decodeTimeStamp: .invalid)
    var sample: CMSampleBuffer?
    CMSampleBufferCreateReadyWithImageBuffer(allocator: kCFAllocatorDefault, imageBuffer: destination,
      formatDescription: description, sampleTiming: &timing, sampleBufferOut: &sample)
    if let sample {
      // Immediate display lets AVKit use its own sample-buffer timebase.
      if let attachments = CMSampleBufferGetSampleAttachmentsArray(sample, createIfNecessary: true) as? [NSMutableDictionary], let first = attachments.first {
        first[kCMSampleAttachmentKey_DisplayImmediately] = true
      }
      layer.enqueue(sample)
      if pip?.isPictureInPicturePossible == true && pendingResult != nil { pip?.startPictureInPicture() }
    }
  }

  private func drawComments(_ buffer: CVPixelBuffer, position: Double, width: CGFloat, height: CGFloat) {
    active.removeAll { position - $0.start > 7 }
    let rows = min(6, max(1, Int(height * area / (fontSize + 8))))
    while commentIndex < comments.count {
      let comment = comments[commentIndex]
      let time = comment["time"] as? Double ?? 0
      if time > position { break }
      commentIndex += 1
      guard position - time < 0.6, let text = comment["text"] as? String,
        let lane = (0..<rows).first(where: { laneEnds[$0] <= position }) else { continue }
      let mode = comment["mode"] as? Int ?? 1
      let rgb = comment["color"] as? Int ?? 0xFFFFFF
      let color = UIColor(red: CGFloat((rgb >> 16) & 255) / 255,
        green: CGFloat((rgb >> 8) & 255) / 255, blue: CGFloat(rgb & 255) / 255, alpha: opacity)
      active.append((String(text.prefix(120)), color, mode, time, lane))
      laneEnds[lane] = position + (mode == 4 || mode == 5 ? 7 : 2)
    }
    CVPixelBufferLockBaseAddress(buffer, [])
    defer { CVPixelBufferUnlockBaseAddress(buffer, []) }
    guard let context = CGContext(data: CVPixelBufferGetBaseAddress(buffer), width: Int(width),
      height: Int(height), bitsPerComponent: 8, bytesPerRow: CVPixelBufferGetBytesPerRow(buffer),
      space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.premultipliedFirst.rawValue | CGBitmapInfo.byteOrder32Little.rawValue) else { return }
    context.translateBy(x: 0, y: height); context.scaleBy(x: 1, y: -1)
    UIGraphicsPushContext(context)
    defer { UIGraphicsPopContext() }
    for comment in active {
      let attributes: [NSAttributedString.Key: Any] = [
        .font: UIFont.systemFont(ofSize: fontSize, weight: .semibold),
        .foregroundColor: comment.color, .strokeColor: UIColor.black.withAlphaComponent(opacity), .strokeWidth: -3]
      let text = comment.text as NSString
      let size = text.size(withAttributes: attributes)
      let fraction = CGFloat((position - comment.start) / 7)
      let x: CGFloat
      if comment.mode == 4 || comment.mode == 5 { x = (width - size.width) / 2 }
      else if comment.mode == 6 { x = -size.width + (width + size.width) * fraction }
      else { x = width - (width + size.width) * fraction }
      let y = comment.mode == 4 ? height - CGFloat(comment.lane + 1) * (fontSize + 8)
        : CGFloat(comment.lane) * (fontSize + 8) + 8
      text.draw(at: CGPoint(x: x, y: y), withAttributes: attributes)
    }
  }

  private func fail(_ message: String) {
    let result = pendingResult; pendingResult = nil
    cleanup(report: result == nil)
    result?(FlutterError(code: "pip_failed", message: message, details: nil))
    if result == nil { channel.invokeMethod("error", arguments: message) }
  }
  private func cleanup(report: Bool) {
    sessionID = UUID()
    let position = video?.currentTime().seconds ?? initialPosition
    let wasPlaying = playing
    pendingResult?(FlutterError(code: "cancelled", message: "画中画已关闭", details: nil)); pendingResult = nil
    possibleObservation = nil; statusObservation = nil; audioObservation = nil
    pip?.delegate = nil
    if pip?.isPictureInPictureActive == true { pip?.stopPictureInPicture() }
    timer?.invalidate(); timer = nil
    video?.pause(); audio?.pause(); video = nil; audio = nil; output = nil
    layer.flushAndRemoveImage(); layer.removeFromSuperlayer(); sourceView.removeFromSuperview()
    pip = nil; pool = nil; timebase = nil; lastImage = nil; prepared = false; lastReported = -1; lastReportedPlaying = nil; lastPosition = -1
    active.removeAll(); comments.removeAll(); commentIndex = 0
    if report { channel.invokeMethod("stopped", arguments: ["position": position.isFinite ? position : initialPosition, "playing": wasPlaying]) }
  }
  func pictureInPictureControllerDidStartPictureInPicture(_ controller: AVPictureInPictureController) {
    possibleObservation = nil
    // AVKit consumes the display layer directly; keep its source attached without
    // covering Flutter controls or pages while the system window is active.
    sourceView.alpha = 0.001
    let result = pendingResult; pendingResult = nil; result?(nil)
  }
  func pictureInPictureController(_ controller: AVPictureInPictureController, failedToStartPictureInPictureWithError error: Error) {
    fail("画中画启动失败：\(error.localizedDescription)")
  }
  func pictureInPictureControllerDidStopPictureInPicture(_ controller: AVPictureInPictureController) { cleanup(report: true) }
  func pictureInPictureController(_ controller: AVPictureInPictureController,
    restoreUserInterfaceForPictureInPictureStopWithCompletionHandler completionHandler: @escaping (Bool) -> Void) {
    channel.invokeMethod("restore", arguments: nil)
    completionHandler(true)
  }
  func pictureInPictureController(_ controller: AVPictureInPictureController, setPlaying playing: Bool) { setPlaying(playing) }
  func pictureInPictureControllerTimeRangeForPlayback(_ controller: AVPictureInPictureController) -> CMTimeRange {
    live ? CMTimeRange(start: .negativeInfinity, duration: .positiveInfinity)
      : CMTimeRange(start: .zero, duration: CMTime(seconds: max(1, duration), preferredTimescale: 600))
  }
  func pictureInPictureControllerIsPlaybackPaused(_ controller: AVPictureInPictureController) -> Bool { !playing }
  func pictureInPictureController(_ controller: AVPictureInPictureController,
    skipByInterval interval: CMTime, completion completionHandler: @escaping () -> Void) {
    let target = min(max(0, (video?.currentTime().seconds ?? 0) + interval.seconds), max(0, duration - 0.1))
    seek(target) { [weak self] in self?.setPlaying(self?.playing ?? false); completionHandler() }
  }
  func pictureInPictureController(_ controller: AVPictureInPictureController, didTransitionToRenderSize newRenderSize: CMVideoDimensions) {}
}
