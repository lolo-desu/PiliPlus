import 'dart:io' show Platform;
import 'dart:ui' as ui;

import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';

/// Native iOS 26 material beneath the existing Flutter controls. Their hit
/// targets, badges, ordering and callbacks stay in Flutter.
class IosGlassSurface extends StatelessWidget {
  const IosGlassSurface({super.key, required this.child, this.radius = 28});
  final Widget child;
  final double radius;
  static Widget wrap(Widget child, {double radius = 28}) =>
      Platform.isIOS ? IosGlassSurface(radius: radius, child: child) : child;
  @override
  Widget build(BuildContext context) => Stack(
    children: [
      Positioned.fill(
        child: ExcludeSemantics(
          child: IgnorePointer(
            child: UiKitView(
              key: ValueKey((
                Theme.of(context).brightness,
                MediaQuery.highContrastOf(context),
                radius,
              )),
              viewType: 'piliplus/liquid_glass',
              creationParams: {
                'radius': radius,
                'dark': Theme.of(context).brightness == Brightness.dark,
                'opaque': MediaQuery.highContrastOf(context),
              },
              creationParamsCodec: const StandardMessageCodec(),
            ),
          ),
        ),
      ),
      child,
    ],
  );
}

/// Lightweight, bounded glass for repeated list/grid items.
class IosGlassCard extends StatelessWidget {
  const IosGlassCard({super.key, required this.child, this.radius = 12});
  final Widget child;
  final double radius;
  @override
  Widget build(BuildContext context) {
    if (!Platform.isIOS) return child;
    IosGlassPreferences.initialize();
    final theme = Theme.of(context);
    final dark = theme.brightness == Brightness.dark;
    return ValueListenableBuilder<bool>(
      valueListenable: IosGlassPreferences.reduceTransparency,
      builder: (context, reduce, _) {
        final opaque = reduce || MediaQuery.highContrastOf(context);
        return ClipRRect(
          borderRadius: BorderRadius.circular(radius),
          child: BackdropFilter.grouped(
            enabled: !opaque,
            filter: ui.ImageFilter.blur(sigmaX: 8, sigmaY: 8),
            child: DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: dark
                      ? [
                          Color(opaque ? 0xFF1C1C1E : 0xC42A2A30),
                          Color(opaque ? 0xFF1C1C1E : 0xB014141A),
                        ]
                      : [
                          Color(opaque ? 0xFFFFFFFF : 0xDCFFFFFF),
                          Color(opaque ? 0xFFFFFFFF : 0xA8EDF2FA),
                        ],
                ),
                border: Border.all(
                  color: dark
                      ? const Color(0x30FFFFFF)
                      : const Color(0xB3FFFFFF),
                  width: 0.7,
                ),
                borderRadius: BorderRadius.circular(radius),
              ),
              child: Theme(
                data: theme.copyWith(
                  cardTheme: theme.cardTheme.copyWith(
                    color: Colors.transparent,
                    surfaceTintColor: Colors.transparent,
                    elevation: 0,
                  ),
                ),
                child: child,
              ),
            ),
          ),
        );
      },
    );
  }
}

class IosGlassPanel extends StatelessWidget {
  const IosGlassPanel({super.key, required this.child});
  final Widget child;
  @override
  Widget build(BuildContext context) {
    if (!Platform.isIOS) return child;
    if (child case final Theme nested) {
      return Theme(
        data: nested.data,
        child: IosGlassPanel(child: nested.child),
      );
    }
    final theme = Theme.of(context);
    return IosGlassSurface(
      radius: 28,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(28),
        child: Theme(
          data: theme.copyWith(
            canvasColor: Colors.transparent,
            scaffoldBackgroundColor: Colors.transparent,
            colorScheme: theme.colorScheme.copyWith(
              surface: Colors.transparent,
            ),
            appBarTheme: theme.appBarTheme.copyWith(
              backgroundColor: Colors.transparent,
              surfaceTintColor: Colors.transparent,
            ),
          ),
          child: child,
        ),
      ),
    );
  }
}

abstract final class IosGlassPreferences {
  static const channel = MethodChannel('piliplus/ios_glass');
  static final reduceTransparency = ValueNotifier(false);
  static bool _initialized = false;
  static void initialize() {
    if (_initialized || !Platform.isIOS) return;
    _initialized = true;
    channel.setMethodCallHandler((call) async {
      if (call.method == 'reduceTransparency') {
        reduceTransparency.value = call.arguments == true;
      }
    });
    channel
        .invokeMethod<bool>('reduceTransparency')
        .then((value) {
          reduceTransparency.value = value ?? false;
        })
        .catchError((Object _) {});
  }
}
