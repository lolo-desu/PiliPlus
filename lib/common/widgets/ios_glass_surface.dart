import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';

/// Native iOS 26 material beneath the existing Flutter controls. Their hit
/// targets, badges, ordering and callbacks stay in Flutter.
class IosGlassSurface extends StatelessWidget {
  const IosGlassSurface({super.key, required this.child, this.radius = 28});
  final Widget child;
  final double radius;
  @override
  Widget build(BuildContext context) => Stack(
    children: [
      Positioned.fill(
        child: ExcludeSemantics(
          child: IgnorePointer(
            child: UiKitView(
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
