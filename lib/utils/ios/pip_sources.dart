import 'package:PiliPlus/models/video/play/url.dart';

/// PiP has its own compatibility ordering; never change full-player preferences.
List<VideoItem> compatiblePipVideos(Iterable<VideoItem> videos, int quality) {
  final result =
      videos.where((video) {
        final codec = video.codecs?.toLowerCase() ?? '';
        return codec.startsWith('avc1') ||
            codec.startsWith('avc3') ||
            video.codecid == 7;
      }).toList()..sort((a, b) {
        int tier(VideoItem v) => v.id == quality
            ? 0
            : v.id < quality
            ? 1
            : 2;
        final order = tier(a).compareTo(tier(b));
        if (order != 0) return order;
        return tier(a) == 1 ? b.id.compareTo(a.id) : a.id.compareTo(b.id);
      });
  return result;
}

AudioItem? compatiblePipAudio(Iterable<AudioItem> audio) {
  final result = audio.where((item) {
    final codec = item.codecs?.toLowerCase() ?? '';
    return codec.startsWith('mp4a') ||
        (codec.isEmpty && const {30216, 30232, 30280}.contains(item.id));
  }).toList()..sort((a, b) => (b.bandWidth ?? 0).compareTo(a.bandWidth ?? 0));
  return result.isEmpty ? null : result.first;
}
