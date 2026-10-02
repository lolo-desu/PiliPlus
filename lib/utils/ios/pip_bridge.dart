import 'package:flutter/services.dart';

/// Native sample-buffer PiP owns playback only while its window is open.
abstract final class IosPipBridge {
  static const channel = MethodChannel('piliplus/ios_pip');
  static Future<void> Function(MethodCall)? onEvent;
  static void initialize() {
    channel.setMethodCallHandler((call) async => onEvent?.call(call));
  }

  static Future<void> start(Map<String, Object?> parameters) async {
    await channel.invokeMethod<void>('start', parameters);
  }

  static Future<void> updateDanmaku(List<Map<String, Object?>> items) async {
    await channel.invokeMethod<void>('danmaku', items);
  }

  static Future<void> dispose() async {
    onEvent = null;
    await channel.invokeMethod<void>('dispose');
  }
}
