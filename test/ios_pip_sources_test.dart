import 'package:PiliPlus/models/video/play/url.dart';
import 'package:PiliPlus/utils/ios/pip_sources.dart';
import 'package:flutter_test/flutter_test.dart';

VideoItem video(int quality, String codec, {int? codecid}) =>
    VideoItem.fromJson({'id': quality, 'codecs': codec, 'codecid': codecid});
AudioItem audio(int quality, String? codec, int bandwidth) =>
    AudioItem.fromJson({
      'id': quality,
      'codecs': codec,
      'bandwidth': bandwidth,
    });

void main() {
  test('PiP prefers current AVC quality and leaves the input unchanged', () {
    final input = [
      video(120, 'avc1.640028'),
      video(80, 'hev1.1.6.L120'),
      video(32, 'avc1.640028'),
      video(80, 'avc3.640028'),
      video(64, 'avc1.640028'),
      video(80, 'av01.0.08M.08'),
    ];
    final original = List<VideoItem>.of(input);
    expect(compatiblePipVideos(input, 80).map((v) => v.id), [80, 64, 32, 120]);
    expect(input, orderedEquals(original));
  });
  test(
    'missing codec uses AVC identifier; unsupported sources are excluded',
    () {
      expect(
        compatiblePipVideos([video(80, '', codecid: 7)], 80),
        hasLength(1),
      );
      expect(
        compatiblePipVideos([video(80, 'hev1'), video(80, 'av01')], 80),
        isEmpty,
      );
    },
  );
  test('PiP chooses highest bandwidth AAC and excludes lossless and Dolby', () {
    final low = audio(30216, null, 64000);
    final high = audio(30280, 'mp4a.40.2', 192000);
    expect(
      compatiblePipAudio([
        audio(30251, 'fLaC', 1000000),
        low,
        audio(30250, 'ec-3', 640000),
        high,
      ]),
      same(high),
    );
    expect(compatiblePipAudio([audio(30251, null, 1000000)]), isNull);
    expect(compatiblePipAudio([]), isNull);
  });
}
