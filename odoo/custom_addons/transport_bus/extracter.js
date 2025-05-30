const fs = require('fs');
const path = require('path');
  
const sourceFolder = 'D:/easycom/PFE-Next.js/typescript-version/full-version/src';
 // Change this to the path of your source folder
const outputFile = './output.txt'; // Change this to the desired output file path
const extensions = ['.js','mjs','ts','tsx','json','d.ts',]; // files that end with extentions that you want

function concatenateFiles(folderPath, outputFilePath, depth = 0) {
  const files = fs.readdirSync(folderPath);
 
  let fileContent = '';
  let folderContent = '';
  let subfolderContent = '';

  files.forEach(file => {
    const filePath = path.join(folderPath, file);

    if (fs.statSync(filePath).isDirectory()) {
      subfolderContent = concatenateFiles(filePath, outputFilePath, depth + 1);

      if (subfolderContent && subfolderContent.trim()) {
        folderContent += `\n\n\n\n\n\n\n\n// ${'  '.repeat(depth)}${file}\n${subfolderContent}\n\n`;
      } else {
        folderContent += subfolderContent;
      }
    } else {
      for (const extension of extensions) {
        if (file.endsWith(extension)) {
          const fileContentToAdd = fs.readFileSync(filePath, 'utf-8');
          fileContent += `\n\n\n\n\n\n\n\n// ${path.join(folderPath, file)}\n${fileContentToAdd}`;
          break;
        }
      }
    }
  });

  const content = folderContent + '\n\n' + fileContent;
  fs.appendFileSync(outputFilePath, content, 'utf-8');
}

concatenateFiles(sourceFolder, outputFile);
console.log('Files concatenated successfully!');
