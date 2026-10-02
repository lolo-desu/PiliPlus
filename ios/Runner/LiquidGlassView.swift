import Flutter
import SwiftUI
import UIKit

private struct GlassMaterial: View {
  let radius: CGFloat
  let opaque: Bool
  var body: some View {
    if opaque {
      RoundedRectangle(cornerRadius: radius).fill(Color(uiColor: .secondarySystemBackground))
    } else if #available(iOS 26.0, *) {
      Color.clear.glassEffect(.regular, in: .rect(cornerRadius: radius))
    } else {
      RoundedRectangle(cornerRadius: radius).fill(.ultraThinMaterial)
    }
  }
}

final class LiquidGlassFactory: NSObject, FlutterPlatformViewFactory {
  private let channel: FlutterMethodChannel
  private var observer: NSObjectProtocol?
  init(messenger: FlutterBinaryMessenger) {
    channel = FlutterMethodChannel(name: "piliplus/ios_glass", binaryMessenger: messenger)
    super.init()
    channel.setMethodCallHandler { call, result in
      if call.method == "reduceTransparency" { result(UIAccessibility.isReduceTransparencyEnabled) }
      else { result(FlutterMethodNotImplemented) }
    }
    observer = NotificationCenter.default.addObserver(
      forName: UIAccessibility.reduceTransparencyStatusDidChangeNotification,
      object: nil, queue: .main) { [weak self] _ in
        self?.channel.invokeMethod("reduceTransparency", arguments: UIAccessibility.isReduceTransparencyEnabled)
      }
  }
  deinit { if let observer { NotificationCenter.default.removeObserver(observer) } }
  func createArgsCodec() -> FlutterMessageCodec & NSObjectProtocol { FlutterStandardMessageCodec.sharedInstance() }
  func create(withFrame frame: CGRect, viewIdentifier viewId: Int64, arguments args: Any?) -> FlutterPlatformView {
    LiquidGlassView(frame: frame, arguments: args)
  }
}

private final class LiquidGlassView: NSObject, FlutterPlatformView {
  private let host: UIHostingController<GlassMaterial>
  private var transparencyObserver: NSObjectProtocol?
  init(frame: CGRect, arguments: Any?) {
    let args = arguments as? [String: Any] ?? [:]
    host = UIHostingController(rootView: GlassMaterial(
      radius: CGFloat((args["radius"] as? NSNumber)?.doubleValue ?? 28),
      opaque: (args["opaque"] as? Bool ?? false) || UIAccessibility.isReduceTransparencyEnabled))
    super.init()
    host.view.frame = frame
    host.view.backgroundColor = .clear
    host.view.isUserInteractionEnabled = false
    host.overrideUserInterfaceStyle = (args["dark"] as? Bool ?? false) ? .dark : .light
    let radius = CGFloat((args["radius"] as? NSNumber)?.doubleValue ?? 28)
    let forcedOpaque = args["opaque"] as? Bool ?? false
    transparencyObserver = NotificationCenter.default.addObserver(
      forName: UIAccessibility.reduceTransparencyStatusDidChangeNotification,
      object: nil, queue: .main) { [weak self] _ in
        self?.host.rootView = GlassMaterial(radius: radius,
          opaque: forcedOpaque || UIAccessibility.isReduceTransparencyEnabled)
      }
  }
  deinit { if let transparencyObserver { NotificationCenter.default.removeObserver(transparencyObserver) } }
  func view() -> UIView { host.view }
}
