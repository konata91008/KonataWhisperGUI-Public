#!/usr/bin/env bash
set -euo pipefail
TJK_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TJK_SOURCE="$TJK_ROOT/build/ffmpeg-9.0.2"
TJK_BUILD="$TJK_ROOT/build/ffmpeg-build"
TJK_NATIVE="$TJK_ROOT/build/native"
mkdir -p "$TJK_BUILD" "$TJK_NATIVE"
cd "$TJK_BUILD"
TJK_ARGS=(
  --disable-autodetect --disable-gpl --disable-nonfree --disable-network
  --disable-everything --disable-shared --enable-static --disable-doc
  --disable-debug --disable-ffplay --disable-ffprobe --disable-avdevice
  --disable-swscale --enable-ffmpeg --enable-swresample
  --enable-protocol=file,pipe
  --enable-demuxer=mov,matroska,avi,asf,wav,mp3,ogg,flac,aac,ac3,eac3,aiff,au,ape,mpc,mpc8,tta,wv,mpegts,mpegps
  --enable-decoder=aac,aac_fixed,aac_latm,alac,flac,mp3,mp3float,mp3adu,mp3adufloat,mp3on4,mp3on4float,mp2,mp2float,opus,vorbis,ac3,ac3_fixed,eac3,wmav1,wmav2,wmapro,wmalossless,wmavoice,ape,tta,wavpack,adpcm_ima_wav,adpcm_ms
  --enable-decoder=pcm_s16le,pcm_s16be,pcm_u8,pcm_s8,pcm_s24le,pcm_s24be,pcm_s32le,pcm_s32be,pcm_f32le,pcm_f32be,pcm_f64le,pcm_f64be,pcm_alaw,pcm_mulaw,pcm_s64le,pcm_s64be
  --enable-parser=aac,aac_latm,ac3,flac,mpegaudio,opus,vorbis
  --enable-encoder=pcm_s16le --enable-muxer=wav
  --enable-filter=aresample,aformat,anull
)
case "$(uname -s)" in
  MINGW*|MSYS*) TJK_ARGS+=(--target-os=mingw32 --arch=x86_64 --disable-x86asm --extra-ldflags=-static); TJK_EXE=ffmpeg.exe ;;
  Darwin) TJK_ARGS+=(--disable-x86asm); TJK_EXE=ffmpeg ;;
  *) echo 'Only macOS and Windows are release targets' >&2; exit 1 ;;
esac
bash "$TJK_SOURCE/configure" "${TJK_ARGS[@]}"
make -j4
cp "$TJK_EXE" "$TJK_NATIVE/$TJK_EXE"
"$TJK_NATIVE/$TJK_EXE" -version
