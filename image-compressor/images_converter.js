import sharp from 'sharp';
import { cpus } from 'os';
import { join, parse } from 'path';
import { readdir, mkdir, stat } from 'fs/promises';
import { Worker, isMainThread, parentPort, workerData } from 'worker_threads';
import { fileURLToPath } from 'url';
import { dirname } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

function formatFilename(filename) {
  return filename.toLowerCase()
    .replace(/\s+/g, '-')
    .replace(/[^a-z0-9-_]/g, '');
}

function getSupportedFormats() {
  return ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.avif', '.tiff'];
}

async function getImageSizeKB(filePath) {
  const stats = await stat(filePath);
  return stats.size / 1024;
}

async function processImage(inputFile, outputDir) {
  const { name, ext } = parse(inputFile);
  const filename = formatFilename(name);
  
  // Create output directories
  const webpOutputDir = join(outputDir, 'webp');
  await mkdir(webpOutputDir, { recursive: true });
  
  const webpOutput = join(webpOutputDir, `${filename}.webp`);
  
  console.log(`\nProcessing ${inputFile}...`);
  
  try {
    // Get original file size
    const originalSize = await getImageSizeKB(inputFile);
    
    // Process image with Sharp
    await sharp(inputFile)
      .webp({
        quality: 80, // Balanced quality
        effort: 4,   // Good compression effort
        lossless: false,
        nearLossless: false
      })
      .toFile(webpOutput);
    
    // Get compressed size
    const webpSize = await getImageSizeKB(webpOutput);
    
    console.log('\nCompression results:');
    console.log(`Original: ${originalSize.toFixed(2)}KB`);
    console.log(`WebP: ${webpSize.toFixed(2)}KB (${(webpSize/originalSize*100).toFixed(1)}%)`);
    
    return {
      filename,
      originalSize,
      webpSize,
      success: true
    };
    
  } catch (error) {
    console.error(`Error processing ${inputFile}`);
    console.error(`Error message: ${error.message}`);
    return {
      filename,
      error: error.message,
      success: false
    };
  }
}

// Worker thread function
if (!isMainThread) {
  const { inputFile, outputDir } = workerData;
  processImage(inputFile, outputDir)
    .then(result => parentPort.postMessage(result))
    .catch(error => parentPort.postMessage({ success: false, error: error.message }));
}

// Main thread function
async function batchProcessImages(inputDir, outputDir) {
  const supportedFormats = getSupportedFormats();
  
  // Get all files from directory
  const allFiles = await readdir(inputDir, { withFileTypes: true });
  
  // Filter supported image files
  const imageFiles = allFiles
    .filter(file => file.isFile() && supportedFormats.includes(parse(file.name).ext.toLowerCase()))
    .map(file => join(inputDir, file.name));
    
  const unsupportedFiles = allFiles
    .filter(file => file.isFile() && !supportedFormats.includes(parse(file.name).ext.toLowerCase()))
    .map(file => file.name);
  
  if (imageFiles.length === 0) {
    console.log('No supported image files found in input directory');
    return;
  }
  
  console.log('\n=== File Analysis ===');
  console.log(`Total files in directory: ${allFiles.length}`);
  console.log(`Supported image files: ${imageFiles.length}`);
  
  // Display found formats details
  const formatCount = {};
  imageFiles.forEach(file => {
    const ext = parse(file).ext.toLowerCase();
    formatCount[ext] = (formatCount[ext] || 0) + 1;
  });
  
  console.log('\nFound formats:');
  Object.entries(formatCount).forEach(([fmt, count]) => {
    console.log(`- ${fmt}: ${count} files`);
  });
  
  if (unsupportedFiles.length > 0) {
    console.log('\nIgnored files:');
    unsupportedFiles.forEach(file => console.log(`- ${file}`));
  }
  
  const maxWorkers = Math.max(1, cpus().length - 1);
  console.log(`\nStarting processing with ${maxWorkers} parallel workers`);
  console.log(`Total images to process: ${imageFiles.length}\n`);
  
  // Process images using worker threads
  const results = await Promise.all(
    imageFiles.map(file => {
      return new Promise((resolve) => {
        const worker = new Worker(__filename, {
          workerData: { inputFile: file, outputDir },
          type: 'module'
        });
        
        worker.on('message', resolve);
        worker.on('error', error => resolve({ success: false, error: error.message }));
      });
    })
  );
  
  console.log('\n=== Processing Summary ===');
  const successful = results.filter(r => r.success);
  const failed = results.filter(r => !r.success);
  
  console.log(`\nSuccessfully processed images: ${successful.length}`);
  console.log(`Failed: ${failed.length}`);
  
  if (failed.length > 0) {
    console.log('\nFailed files:');
    failed.forEach(result => {
      console.log(`- ${result.filename}: ${result.error || 'Unknown error'}`);
    });
  }
  
  if (successful.length > 0) {
    const totalOriginal = successful.reduce((sum, r) => sum + r.originalSize, 0);
    const totalWebp = successful.reduce((sum, r) => sum + r.webpSize, 0);
    
    console.log('\nTotal size reduction:');
    console.log(`Original: ${totalOriginal.toFixed(2)}KB`);
    console.log(`WebP: ${totalWebp.toFixed(2)}KB (ratio: ${(totalWebp/totalOriginal*100).toFixed(1)}%)`);
  }
}

// Main execution
if (isMainThread) {
  const INPUT_DIR = 'images_input';
  const OUTPUT_DIR = 'images_output';
  
  batchProcessImages(INPUT_DIR, OUTPUT_DIR)
    .catch(console.error);
}
