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
  func createArgsCodec() -> FlutterMessageCodec & NSObjectProtocol { FlutterStandardMessageCodec.sharedInstance() }
  func create(withFrame frame: CGRect, viewIdentifier viewId: Int64, arguments args: Any?) -> FlutterPlatformView {
    LiquidGlassView(frame: frame, arguments: args)
  }
}

private final class LiquidGlassView: NSObject, FlutterPlatformView {
  private let host: UIHostingController<GlassMaterial>
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
  }
  func view() -> UIView { host.view }
}
