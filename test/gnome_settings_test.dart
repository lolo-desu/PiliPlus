import 'dart:io';
import 'dart:ui' as ui;

import 'package:PiliPlus/pages/setting/view.dart';
import 'package:PiliPlus/utils/accounts.dart';
import 'package:PiliPlus/utils/accounts/account.dart';
import 'package:PiliPlus/utils/storage.dart';
import 'package:PiliPlus/utils/gnome_theme.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hive_ce/hive.dart';
import 'package:material_ui/material_ui.dart';

void main() {
  late Directory tempDir;
  setUpAll(() async {
    tempDir = await Directory.systemTemp.createTemp('pili-gnome-ui-');
    Hive.init(tempDir.path);
    GStorage.regAdapter();
    Accounts.account = await Hive.openBox<LoginAccount>('account');
    GStorage.setting = await Hive.openBox('setting');
    GStorage.video = await Hive.openBox('video');
    GStorage.localCache = await Hive.openBox('localCache');
  });
  tearDownAll(() async {
    await Hive.close();
    await tempDir.delete(recursive: true);
  });
  for (final width in [420.0, 1280.0]) {
    for (final brightness in Brightness.values) {
      testWidgets('Settings remain reachable at $width $brightness', (
        tester,
      ) async {
        debugDefaultTargetPlatformOverride = TargetPlatform.linux;
        tester.view.physicalSize = Size(width, 900);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        for (final entry in {
          'ScreenshotFont': 'GNOME_TEST_FONT',
          'MaterialIcons': 'GNOME_ICON_FONT',
          'packages/material_design_icons_flutter/Material Design Icons':
              'GNOME_MDI_FONT',
        }.entries) {
          final path = Platform.environment[entry.value];
          if (path != null) {
            final loader = FontLoader(entry.key)..addFont(
              Future.value(ByteData.sublistView(File(path).readAsBytesSync())),
            );
            await tester.runAsync(loader.load);
          }
        }
        final captureKey = GlobalKey();
        await tester.pumpWidget(
          MaterialApp(
            theme: GnomeTheme.apply(
              ThemeData(
                brightness: brightness,
                colorSchemeSeed: const Color(0xff3584e4),
                fontFamily: 'ScreenshotFont',
              ),
            ),
            home: RepaintBoundary(key: captureKey, child: const SettingPage()),
          ),
        );
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
        final captureDirectory = Platform.environment['GNOME_CAPTURE_DIR'];
        if (captureDirectory != null) {
          final boundary =
              captureKey.currentContext!.findRenderObject()!
                  as RenderRepaintBoundary;
          await tester.runAsync(() async {
            final image = await boundary.toImage();
            final bytes = await image.toByteData(
              format: ui.ImageByteFormat.png,
            );
            final file = File(
              '$captureDirectory/piliplus-settings-${width.toInt()}-${brightness.name}.png',
            );
            await file.parent.create(recursive: true);
            await file.writeAsBytes(bytes!.buffer.asUint8List());
            image.dispose();
          });
        }
        for (final label in [
          '隐私设置',
          '推荐流设置',
          '音视频设置',
          '播放器设置',
          '外观设置',
          '其它设置',
          'WebDAV 设置',
          '切换账号',
          '关于',
        ]) {
          final destination = find.text(label).last;
          expect(destination, findsOneWidget);
          await tester.ensureVisible(destination);
        }
        // Verify the desktop split pane switches using the real setting page.
        if (width > 900) {
          await tester.ensureVisible(find.text('推荐流设置'));
          await tester.tap(find.text('推荐流设置'));
          await tester.pumpAndSettle();
          expect(find.text('推荐流设置'), findsNWidgets(2));
        }
        expect(tester.takeException(), isNull);
        debugDefaultTargetPlatformOverride = null;
      });
    }
  }
}
